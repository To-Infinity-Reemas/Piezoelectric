#include <Wire.h>
#include <MPU6050.h>
#include <LiquidCrystal.h>

// تعريف شاشة LCD
LiquidCrystal lcd(7, 8, 12, 11, 9, 10);

// تعريف الحساسات
MPU6050 mpu;
const int led = 3;
const int led1 = 1;
const int sensor = A5;

// متغيرات الجهد وحساب الخطوات
float input_voltage = 0.0;
float last_input = 0.0;
float temp = 0.0;
float r1 = 100000.0;
float r2 = 10000.0;
int stepCount = 0;
long y = 0;

void setup() {
    Serial.begin(9600);
    Wire.begin();
    mpu.initialize();

    // التحقق من اتصال حساس MPU6050
    if (!mpu.testConnection()) {
        Serial.println("خطأ: لم يتم الاتصال بحساس MPU6050");
        while (1);
    }

    // إعدادات Arduino
    pinMode(led, OUTPUT);
    pinMode(led1, OUTPUT);
    lcd.begin(16, 2);

    // عرض رسالة ترحيبية
    lcd.print(" FootStep Power ");
    lcd.setCursor(0, 1);
    lcd.print("   Generator    ");
    delay(2000);
    lcd.clear();
}

void loop() {
    //  قراءة بيانات الجهد وحساب عدد الخطوات 
    int analog_value = analogRead(sensor);
    temp = (analog_value * 5.0) / 1024.0;
    input_voltage = temp / (r2 / (r1 + r2));

    if (input_voltage < 0.1) {
        input_voltage = 0.0;
    }

    if ((last_input < input_voltage) && (input_voltage > 5)) {
        lcd.clear();
        y = millis();
        digitalWrite(led1, HIGH);
        digitalWrite(led, LOW);

        if (last_input == 0) {
            stepCount++;
        }
        last_input = input_voltage;

        Serial.print("v= ");
        Serial.println(input_voltage);
        Serial.print("Step Count: ");
        Serial.println(stepCount);

        lcd.print("Voltage: ");
        lcd.print(input_voltage);
        lcd.print(" V ");
        lcd.setCursor(0, 1);
        lcd.print("Steps: ");
        lcd.print(stepCount);
    }

    if (millis() > y + 1000) {
        last_input = 0;
        digitalWrite(led, HIGH);
        digitalWrite(led1, LOW);
    }

    //  قراءة بيانات التسارع والجيروسكوب من MPU6050 
    int16_t ax, ay, az, gx, gy, gz;
    mpu.getMotion6(&ax, &ay, &az, &gx, &gy, &gz);

    Serial.print("AccelX: "); Serial.print(ax);
    Serial.print(" | AccelY: "); Serial.print(ay);
    Serial.print(" | AccelZ: "); Serial.println(az);

    Serial.print("GyroX: "); Serial.print(gx);
    Serial.print(" | GyroY: "); Serial.print(gy);
    Serial.print(" | GyroZ: "); Serial.println(gz);

    delay(100000000);
}
