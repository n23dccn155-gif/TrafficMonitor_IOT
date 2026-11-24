// TrafficMonitor IoT: Uno R3, USB Serial at 9600 baud.
// A: red D2, yellow D3, green D4. B: red D5, yellow D6, green D7.
// Commands: STATUS, AUTO <aGreen> <aYellow> <bGreen> <bYellow>,
//           MANUAL <A_GREEN|A_YELLOW|B_GREEN|B_YELLOW|ALL_YELLOW|ALL_RED>.
// Response: STATE <phase> <remaining_ms> <aGreen> <aYellow> <bGreen> <bYellow> <mode>
// Safety: handing right of way to the other road always runs
//   own yellow -> ALL_RED (3 s) -> target, so both roads are never green together.
#include <stdio.h>
#include <string.h>

const byte pins[] = {2, 3, 4, 5, 6, 7};
const char *phases[] = {"A_GREEN", "A_YELLOW", "B_GREEN", "B_YELLOW", "ALL_RED", "ALL_YELLOW"};
enum Phase { A_GREEN, A_YELLOW, B_GREEN, B_YELLOW, ALL_RED, ALL_YELLOW };
const unsigned long ALL_RED_MS = 3000;  // Clearance: both roads red between directions.
Phase phase = ALL_RED;
Phase pendingPhase = ALL_RED;  // Target of a safe transition still in progress.
bool hasPending = false;
bool automatic = true;  // Run the cycle on power-up without the web.
unsigned long phaseStarted = 0;
unsigned long durations[] = {15000, 3000, 15000, 3000};  // Indexed by A_GREEN..B_YELLOW.
char command[80];
byte commandLength = 0;

void showPhase(Phase next) {
  // Turn every lamp off before enabling the requested pair.
  for (byte i = 0; i < 6; ++i) digitalWrite(pins[i], LOW);
  phase = next;
  phaseStarted = millis();
  if (next == A_GREEN) { digitalWrite(4, HIGH); digitalWrite(5, HIGH); }
  if (next == A_YELLOW) { digitalWrite(3, HIGH); digitalWrite(5, HIGH); }
  if (next == B_GREEN) { digitalWrite(2, HIGH); digitalWrite(7, HIGH); }
  if (next == B_YELLOW) { digitalWrite(2, HIGH); digitalWrite(6, HIGH); }
  if (next == ALL_RED) { digitalWrite(2, HIGH); digitalWrite(5, HIGH); }
  if (next == ALL_YELLOW) { digitalWrite(3, HIGH); digitalWrite(6, HIGH); }
}

// 'A', 'B', or 0 for the shared ALL_RED / ALL_YELLOW phases.
char groupOf(Phase p) {
  if (p == A_GREEN || p == A_YELLOW) return 'A';
  if (p == B_GREEN || p == B_YELLOW) return 'B';
  return 0;
}

bool isGreen(Phase p) { return p == A_GREEN || p == B_GREEN; }

// How long the current phase lasts before loop() advances; 0 means hold.
unsigned long stepDuration() {
  if (hasPending) return phase == ALL_RED ? ALL_RED_MS : durations[phase];
  if (!automatic || phase == ALL_YELLOW) return 0;
  return phase == ALL_RED ? ALL_RED_MS : durations[phase];
}

// Moves to `next`, inserting own yellow and/or ALL_RED when the change would
// give right of way to a road while the other road is not yet red.
void requestPhase(Phase next) {
  // ALL_RED shorter than ALL_RED_MS (clearance running, or just reached as a target):
  // never cut it short, only (re)target what follows it.
  if (phase == ALL_RED && (hasPending || millis() - phaseStarted < ALL_RED_MS)) {
    pendingPhase = next;
    hasPending = true;
    return;
  }
  char from = groupOf(phase), to = groupOf(next);
  bool conflict = (from && to && from != to) || (phase == ALL_YELLOW && isGreen(next));
  hasPending = false;
  if (conflict || (next == ALL_RED && from)) {
    pendingPhase = next;
    hasPending = true;
    bool yellowRunning = (phase == A_YELLOW || phase == B_YELLOW) &&
                         millis() - phaseStarted < durations[phase];
    if (phase == A_GREEN) showPhase(A_YELLOW);
    else if (phase == B_GREEN) showPhase(B_YELLOW);
    else if (!yellowRunning) showPhase(ALL_RED);  // A running yellow finishes first (advance()).
  } else {
    showPhase(next);
  }
}

Phase nextAutoPhase() {
  if (phase == A_GREEN) return A_YELLOW;
  if (phase == A_YELLOW) return B_GREEN;  // requestPhase inserts ALL_RED.
  if (phase == B_GREEN) return B_YELLOW;
  return A_GREEN;  // After B_YELLOW (via ALL_RED) or from ALL_RED at start-up.
}

void advance() {
  if (!hasPending) { requestPhase(nextAutoPhase()); return; }
  if (phase != ALL_RED) {           // Own yellow finished: clear the box.
    showPhase(ALL_RED);
    if (pendingPhase == ALL_RED) hasPending = false;
  } else {                          // Clearance finished: enter the target.
    hasPending = false;
    showPhase(pendingPhase);
  }
}

void reportState() {
  unsigned long duration = stepDuration();
  unsigned long elapsed = millis() - phaseStarted;
  unsigned long remaining = elapsed >= duration ? 0 : duration - elapsed;
  Serial.print(F("STATE "));
  Serial.print(phases[phase]); Serial.print(' ');
  Serial.print(remaining);
  for (byte i = 0; i < 4; ++i) { Serial.print(' '); Serial.print(durations[i] / 1000); }
  Serial.print(' '); Serial.println(automatic ? F("AUTO") : F("MANUAL"));
}

void handleCommand(char *line) {
  if (strcmp(line, "STATUS") == 0) { reportState(); return; }
  unsigned int ag, ay, bg, by;
  char extra;
  if (sscanf(line, "AUTO %u %u %u %u %c", &ag, &ay, &bg, &by, &extra) == 4 &&
      ag >= 3 && ag <= 120 && bg >= 3 && bg <= 120 &&
      ay >= 1 && ay <= 10 && by >= 1 && by <= 10) {
    durations[0] = (unsigned long)ag * 1000;
    durations[1] = (unsigned long)ay * 1000;
    durations[2] = (unsigned long)bg * 1000;
    durations[3] = (unsigned long)by * 1000;
    automatic = true;
    requestPhase(A_GREEN);
    reportState();
    return;
  }
  if (strncmp(line, "MANUAL ", 7) == 0) {
    for (byte i = 0; i < 6; ++i) {
      if (strcmp(line + 7, phases[i]) == 0) {
        automatic = false;
        requestPhase((Phase)i);
        reportState();
        return;
      }
    }
  }
  Serial.println(F("ERROR invalid_command"));
}

void setup() {
  for (byte i = 0; i < 6; ++i) { pinMode(pins[i], OUTPUT); digitalWrite(pins[i], LOW); }
  showPhase(ALL_RED);  // Start with both roads red; AUTO moves to A_GREEN after 3 s.
  Serial.begin(9600);
}

void loop() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      command[commandLength] = '\0';
      if (commandLength && command[commandLength - 1] == '\r') command[--commandLength] = '\0';
      handleCommand(command);
      commandLength = 0;
    } else if (commandLength < sizeof(command) - 1) {
      command[commandLength++] = c;
    } else {
      commandLength = 0;
      Serial.println(F("ERROR command_too_long"));
    }
  }
  unsigned long duration = stepDuration();
  if (duration && millis() - phaseStarted >= duration) advance();
}
