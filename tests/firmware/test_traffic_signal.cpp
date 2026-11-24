// Host-side test for arduino/traffic_signal/traffic_signal.ino: stubs the Arduino APIs and
// checks the safety invariants (never both green, every change of direction runs the
// yellow to its end and then ALL_RED >= 3000 ms). No Arduino toolchain needed:
//   g++ -std=c++17 -static tests/firmware/test_traffic_signal.cpp -o test_traffic_signal && ./test_traffic_signal
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
typedef unsigned char byte;
#define F(x) x
#define HIGH 1
#define LOW 0
#define OUTPUT 1
static unsigned long fakeMillis = 0;
static int pinState[16];
unsigned long millis() { return fakeMillis; }
void pinMode(int, int) {}
void digitalWrite(int p, int v) { pinState[p] = v; }
static std::string input, output;
struct FakeSerial {
  void begin(int) {}
  int available() { return (int)input.size(); }
  char read() { char c = input[0]; input.erase(0, 1); return c; }
  void print(const char *s) { output += s; }
  void print(char c) { output += c; }
  void print(unsigned long v) { output += std::to_string(v); }
  void println(const char *s) { output += s; output += '\n'; }
} Serial;
#ifndef TRAFFIC_INO
#define TRAFFIC_INO "../../arduino/traffic_signal/traffic_signal.ino"
#endif
#include TRAFFIC_INO

static int fails = 0;
#define CHECK(c, msg) do { if (!(c)) { printf("FAIL t=%lu: %s\n", fakeMillis, msg); ++fails; } } while (0)

// Lamps: A red 2 yellow 3 green 4, B red 5 yellow 6 green 7.
static std::string lamps() {
  bool aR = pinState[2], aY = pinState[3], aG = pinState[4], bR = pinState[5], bY = pinState[6], bG = pinState[7];
  if (aG && bR) return "A_GREEN"; if (aY && bR) return "A_YELLOW";
  if (aR && bG) return "B_GREEN"; if (aR && bY) return "B_YELLOW";
  if (aR && bR) return "ALL_RED"; if (aY && bY) return "ALL_YELLOW";
  return "INVALID";
}

static std::vector<std::pair<unsigned long, std::string>> trace;
static void step(unsigned long ms) {
  for (unsigned long i = 0; i < ms; i += 10) {
    fakeMillis += 10;
    loop();
    std::string now = lamps();
    CHECK(!(pinState[4] && pinState[7]), "both green");
    CHECK(now != "INVALID", "invalid lamp combination");
    if (trace.empty() || trace.back().second != now) trace.push_back({fakeMillis, now});
  }
}
static void send(const char *cmd) {
  input += cmd; input += '\n'; output.clear(); loop();
  std::string now = lamps();
  if (trace.empty() || trace.back().second != now) trace.push_back({fakeMillis, now});
}

// Every entry into a green that follows the other road's lamps must have ALL_RED >= 3000 ms before it.
static void checkTrace(const char *name) {
  char last = 0;
  for (size_t i = 0; i < trace.size(); ++i) {
    const std::string &p = trace[i].second;
    char g = (p[0] == 'A' || p[0] == 'B') && p[1] == '_' ? p[0] : 0;
    if (p == "ALL_YELLOW") last = 'Y';
    if (g && p.find("GREEN") != std::string::npos && last && last != g) {
      bool ok = i > 0 && trace[i - 1].second == "ALL_RED" && trace[i].first - trace[i - 1].first >= 3000;
      if (!ok) { printf("FAIL %s: %s at %lu without 3 s ALL_RED\n", name, p.c_str(), trace[i].first); ++fails; }
    }
    if (g) last = g;
  }
  printf("%s:", name);
  for (auto &e : trace) printf(" %s@%lu", e.second.c_str(), e.first);
  printf("\n");
  trace.clear();
}

int main() {
  setup();
  CHECK(lamps() == "ALL_RED", "start-up is ALL_RED");
  step(2900); CHECK(lamps() == "ALL_RED", "still ALL_RED at 2.9 s");
  step(200); CHECK(lamps() == "A_GREEN", "A_GREEN after 3 s");
  step(80000); checkTrace("auto");

  send("MANUAL A_GREEN"); step(6200);
  CHECK(lamps() == "A_GREEN", "manual A_GREEN reached");
  send("MANUAL B_GREEN");
  CHECK(lamps() == "A_YELLOW", "manual A->B starts with A yellow");
  CHECK(output.find("STATE A_YELLOW 3000") == 0, "STATE reports yellow remaining");
  step(3000); CHECK(lamps() == "ALL_RED", "then ALL_RED");
  send("STATUS"); CHECK(output.find("STATE ALL_RED 30") == 0, "ALL_RED remaining reported");
  step(1000);
  send("MANUAL A_GREEN");  // During clearance: retarget only.
  CHECK(lamps() == "ALL_RED", "clearance not cut short");
  step(2100); CHECK(lamps() == "A_GREEN", "retargeted to A_GREEN after full 3 s");
  step(20000); CHECK(lamps() == "A_GREEN", "manual green holds");
  checkTrace("manual");

  send("MANUAL ALL_YELLOW"); CHECK(lamps() == "ALL_YELLOW", "all yellow");
  send("MANUAL B_GREEN"); CHECK(lamps() == "ALL_RED", "ALL_YELLOW -> green goes via ALL_RED");
  step(3100); CHECK(lamps() == "B_GREEN", "B_GREEN after clearance");
  send("MANUAL ALL_RED"); CHECK(lamps() == "B_YELLOW", "green -> ALL_RED via yellow");
  step(3100); CHECK(lamps() == "ALL_RED", "ALL_RED reached");
  step(10000); CHECK(lamps() == "ALL_RED", "manual ALL_RED holds");
  checkTrace("all_yellow_and_stop");

  // Second command during the yellow: the yellow still runs its full 3 s.
  send("MANUAL A_GREEN"); step(3100);
  CHECK(lamps() == "A_GREEN", "A_GREEN before double click");
  send("MANUAL B_GREEN"); step(200);
  send("MANUAL B_GREEN"); CHECK(lamps() == "A_YELLOW", "yellow not cut by a 2nd command");
  send("MANUAL ALL_RED"); CHECK(lamps() == "A_YELLOW", "yellow not cut by ALL_RED either");
  step(2700); CHECK(lamps() == "A_YELLOW", "yellow still on at 2.9 s");
  step(200); CHECK(lamps() == "ALL_RED", "ALL_RED after full yellow");
  checkTrace("double_command_during_yellow");

  // ALL_RED reached as the target, then a green 200 ms later: still a full 3 s clearance.
  step(3100);  // Let the previous clearance end first.
  send("MANUAL A_YELLOW"); CHECK(lamps() == "A_YELLOW", "A_YELLOW from settled ALL_RED");
  step(3100);  // Held manual yellow, already past its 3 s.
  send("MANUAL ALL_RED"); CHECK(lamps() == "ALL_RED", "expired yellow -> ALL_RED directly");
  step(200);
  send("MANUAL B_GREEN"); CHECK(lamps() == "ALL_RED", "green waits for clearance");
  step(2700); CHECK(lamps() == "ALL_RED", "still clearing at 2.9 s");
  step(200); CHECK(lamps() == "B_GREEN", "B_GREEN after 3 s ALL_RED");
  checkTrace("target_all_red_then_green");
  send("AUTO 5 2 5 2"); CHECK(lamps() == "B_YELLOW", "AUTO from B_GREEN goes via yellow");
  step(2000 + 3100); CHECK(lamps() == "A_GREEN", "AUTO starts at A_GREEN");
  step(40000); checkTrace("auto_restart");

  // Conflicting MANUAL during the AUTO cycle's yellow: yellow finishes, then ALL_RED 3 s.
  while (lamps() != "A_YELLOW") step(10);
  step(500);
  send("MANUAL B_GREEN"); CHECK(lamps() == "A_YELLOW", "AUTO yellow not cut");
  step(1400); CHECK(lamps() == "A_YELLOW", "AUTO yellow 2 s still running");
  step(200); CHECK(lamps() == "ALL_RED", "then ALL_RED");
  step(3000); CHECK(lamps() == "B_GREEN", "then B_GREEN");
  checkTrace("manual_during_auto_yellow");

  printf(fails ? "FAILED %d\n" : "ALL FIRMWARE CHECKS PASSED\n", fails);
  return fails ? 1 : 0;
}
