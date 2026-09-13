/*
 * Beehaviour - sensor reading on the UNO Q microcontroller.
 *
 * The Modulino modules hang off the Qwiic connector, which on the UNO Q is
 * wired to the microcontroller's second I2C bus (Wire1) and is not visible
 * from the Linux side. So they are read here and every sample is pushed to
 * the Python app over the Bridge.
 *
 * This sketch decides nothing: it reports which sensors it can see and what
 * they read. Aggregation, storage and presentation all live on the Python
 * side.
 *
 * Outside sensor: the Modulino Thermo is an HS3003 with a fixed I2C address
 * (0x44) and no address-select pin, so two of them cannot share the Qwiic
 * bus. A second one would hang off the other bus (Wire, the header's SDA/SCL
 * pins) by instantiating HS300xClass(Wire) directly, bypassing the Modulino
 * wrapper. Waiting on the cable for that.
 */

#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>

ModulinoThermo thermo;
ModulinoMovement movement;

bool haveThermo = false;
bool haveMovement = false;

// Sampling period. Python aggregates before storing, so this sets the pace of
// the live view, not of the history.
const unsigned long SAMPLE_INTERVAL_MS = 2000;

// How often an absent module is retried, so plugging one in works without
// resetting the board.
const unsigned long PROBE_INTERVAL_MS = 5000;

unsigned long lastSample = 0;
unsigned long lastProbe = 0;

void announce() {
  Bridge.notify("sensors_detected", haveThermo, haveMovement);
}

void setup() {
  Bridge.begin();

  // Wire1 is the Qwiic connector on the UNO Q.
  Modulino.begin(Wire1);

  haveThermo = thermo.begin();
  haveMovement = movement.begin();

  announce();
}

void loop() {
  unsigned long now = millis();

  // --- retry absent modules ----------------------------------------------
  if ((!haveThermo || !haveMovement) && now - lastProbe >= PROBE_INTERVAL_MS) {
    lastProbe = now;
    bool changed = false;

    if (!haveThermo && thermo.begin()) {
      haveThermo = true;
      changed = true;
    }
    if (!haveMovement && movement.begin()) {
      haveMovement = true;
      changed = true;
    }
    if (changed) {
      announce();
    }
  }

  // --- sampling -----------------------------------------------------------
  if (now - lastSample < SAMPLE_INTERVAL_MS) {
    return;
  }
  lastSample = now;

  if (haveThermo) {
    float celsius = thermo.getTemperature();
    float humidity = thermo.getHumidity();

    // The library returns NAN when the I2C transaction fails, which is what
    // happens when someone unplugs the module. Give it up and let the retry
    // above pick it back up if it returns.
    if (isnan(celsius) || isnan(humidity)) {
      haveThermo = false;
      announce();
    } else {
      Bridge.notify("thermo_reading", celsius, humidity);
    }
  }

  if (haveMovement) {
    if (movement.update()) {
      Bridge.notify("movement_reading",
                    movement.getX(), movement.getY(), movement.getZ());
    }
  }
}
