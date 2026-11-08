const int SENSOR_PIN = A0;
const int LED_PIN = 3;

const float ALPHA = 0.2;
const float BASELINE = 0.0;

const float CONTACT_ON = 50.0;
const float CONTACT_OFF = 20.0;
const float FULL_SCALE = 900.0;

float ema = 0.0;
bool initialized = false;
bool contact = false;

void setup() {
  pinMode(LED_PIN, OUTPUT);
  analogWrite(LED_PIN, 0);
  Serial.begin(115200);
}

void loop() {
  int raw = analogRead(SENSOR_PIN);

  // 第一个读数用于初始化，之后进行 EMA 平滑
  if (!initialized) {
    ema = raw;
    initialized = true;
  } else {
    ema = ALPHA * raw + (1.0 - ALPHA) * ema;
  }

  float response = ema - BASELINE;
  if (response < 0.0) {
    response = 0.0;
  }

  // 带滞回的接触判断
  if (!contact && response >= CONTACT_ON) {
    contact = true;
  } else if (contact && response <= CONTACT_OFF) {
    contact = false;
  }

  // 未接触时关闭；接触时将响应映射到 PWM
  int pwm = 0;
  if (contact) {
    pwm = (int)(response / FULL_SCALE * 255.0 + 0.5);
    pwm = constrain(pwm, 0, 255);
  }

  analogWrite(LED_PIN, pwm);

  // 保留原来的单整数格式，兼容现有 Python 程序
  Serial.println(raw);

  delay(20);
}