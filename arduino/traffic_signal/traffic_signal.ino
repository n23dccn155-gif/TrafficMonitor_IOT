// TrafficMonitor IoT: Uno R3, USB Serial at 9600 baud.
// A: red D2, yellow D3, green D4. B: red D5, yellow D6, green D7.
// Commands: STATUS, AUTO <aGreen> <aYellow> <bGreen> <bYellow>,
//           MANUAL <A_GREEN|A_YELLOW|B_GREEN|B_YELLOW|ALL_YELLOW|ALL_RED>.
// Response: STATE <phase> <remaining_ms> <aGreen> <aYellow> <bGreen> <bYellow> <mode>
#include <stdio.h>
#include <string.h>

const byte pins[] = {2, 3, 4, 5, 6, 7};
const char *phases[] = {"A_GREEN", "A_YELLOW", "B_GREEN", "B_YELLOW", "ALL_RED", "ALL_YELLOW"};
enum Phase { A_GREEN, A_YELLOW, B_GREEN, B_YELLOW, ALL_RED, ALL_YELLOW };
Phase phase = ALL_RED;
Phase pendingPhase = ALL_RED;
bool automatic = true;  // Start the original 5s green / 2s yellow cycle without the web.
bool transitioning = false;
unsigned long phaseStarted = 0;
unsigned long durations[] = {5000, 2000, 5000, 2000};
const unsigned long clearanceMs = 500;
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

void requestPhase(Phase next) {
  bool crossing = (phase == A_GREEN || phase == A_YELLOW) &&
                  (next == B_GREEN || next == B_YELLOW);
  crossing |= (phase == B_GREEN || phase == B_YELLOW) &&
              (next == A_GREEN || next == A_YELLOW);
  if (crossing) {
    pendingPhase = next;
    transitioning = true;
    showPhase(ALL_RED);
  } else {
    transitioning = false;
    showPhase(next);
  }
}

void reportState() {
  unsigned long remaining = 0;
  if (transitioning) {
    unsigned long elapsed = millis() - phaseStarted;
    remaining = elapsed >= clearanceMs ? 0 : clearanceMs - elapsed;
  } else if (automatic && phase != ALL_RED && phase != ALL_YELLOW) {
    unsigned long elapsed = millis() - phaseStarted;
    remaining = elapsed >= durations[phase] ? 0 : durations[phase] - elapsed;
  }
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
  showPhase(A_GREEN);
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
  unsigned long elapsed = millis() - phaseStarted;
  if (transitioning && elapsed >= clearanceMs) {
    transitioning = false;
    showPhase(pendingPhase);
  } else if (automatic && !transitioning && phase != ALL_RED && phase != ALL_YELLOW && elapsed >= durations[phase]) {
    requestPhase((Phase)((phase + 1) % 4));
  }
}
