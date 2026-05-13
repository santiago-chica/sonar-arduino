#define SERVO_PIN 3
#define TRIGGER_PIN 12
#define ECHO_PIN 11

#define SERVO_MAX 180
#define STEP_DELAY 25
#define ANGLE_AUGMENT 5

#include <Servo.h>
#include <HCSR04.h>

Servo servo;
int angle = 0;

void setup() {
  Serial.begin(9600);
  HCSR04.begin(TRIGGER_PIN, ECHO_PIN);

  servo.attach(SERVO_PIN, 0, SERVO_MAX);
  servo.write(90);
}

double getDistanceInCm() {
  return HCSR04.measureDistanceCm()[0];
}

void sendUpdate() {
  servo.write(angle);

  // JSON

  // { "angle": 50, "distance": 4.6}

  String json = "{\"angle\":";
  json += angle;
  json += ",\"distance\":";
  json += String(getDistanceInCm(), 2);
  json += "}";

  Serial.println(json);

}

void loop() {

  for (angle = 0; angle < SERVO_MAX; angle+=ANGLE_AUGMENT) {
    sendUpdate();
    delay(STEP_DELAY);
  }
  for (angle = SERVO_MAX; angle > 0; angle-=ANGLE_AUGMENT) {
    sendUpdate();
    delay(STEP_DELAY);
  }
}
