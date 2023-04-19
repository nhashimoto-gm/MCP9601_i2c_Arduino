#include "Adafruit_MCP9601.h"
#define I2C_ADDRESS (0x67)
Adafruit_MCP9601 mcp;

// 7-seg
#include <Wire.h>
#define DISPLAY_ADDRESS1 0x20 //This is the change address
int cycles = 0;

static uint8_t recv_cmd[8] = {};

void setup()
{
    Serial.begin(9600);
    while (!Serial) {
      delay(10);
    }
    Serial.println("Adafruit MCP9601 test");

    /* Initialise the driver with I2C_ADDRESS and the default I2C bus. */
    if (! mcp.begin(I2C_ADDRESS)) {
        Serial.println("Sensor not found. Check wiring!");
        while (1);
    }

  Serial.println("Found MCP9601!");

  mcp.setADCresolution(MCP9600_ADCRESOLUTION_18);
  Serial.print("ADC resolution set to ");
  switch (mcp.getADCresolution()) {
    case MCP9600_ADCRESOLUTION_18:   Serial.print("18"); break;
    case MCP9600_ADCRESOLUTION_16:   Serial.print("16"); break;
    case MCP9600_ADCRESOLUTION_14:   Serial.print("14"); break;
    case MCP9600_ADCRESOLUTION_12:   Serial.print("12"); break;
  }
  Serial.println(" bits");

  mcp.setThermocoupleType(MCP9600_TYPE_K);
  Serial.print("Thermocouple type set to ");
  switch (mcp.getThermocoupleType()) {
    case MCP9600_TYPE_K:  Serial.print("K"); break;
    case MCP9600_TYPE_J:  Serial.print("J"); break;
    case MCP9600_TYPE_T:  Serial.print("T"); break;
    case MCP9600_TYPE_N:  Serial.print("N"); break;
    case MCP9600_TYPE_S:  Serial.print("S"); break;
    case MCP9600_TYPE_E:  Serial.print("E"); break;
    case MCP9600_TYPE_B:  Serial.print("B"); break;
    case MCP9600_TYPE_R:  Serial.print("R"); break;
  }
  Serial.println(" type");

  mcp.setFilterCoefficient(3);
  Serial.print("Filter coefficient value set to: ");
  Serial.println(mcp.getFilterCoefficient());

  mcp.setAlertTemperature(1, 30);
  Serial.print("Alert #1 temperature set to ");
  Serial.println(mcp.getAlertTemperature(1));
  mcp.configureAlert(1, true, true);  // alert 1 enabled, rising temp

  mcp.enable(true);

  Serial.println(F("------------------------------"));

  //7-seg setup
  Wire.beginTransmission(DISPLAY_ADDRESS1);
  Wire.write('v');
  Wire.endTransmission();

}

void loop()
{
  uint8_t status = mcp.getStatus();
  
  //Serial.print("MCP Status: 0x"); 
  //Serial.println(status, HEX);  

  /*
  if (status & MCP9601_STATUS_OPENCIRCUIT) { 
    Serial.println("Thermocouple open!"); 
    return; // don't continue, since there's no thermocouple
  }
  if (status & MCP9601_STATUS_SHORTCIRCUIT) { 
    Serial.println("Thermocouple shorted to ground!"); 
    return; // don't continue, since the sensor is not working
  }
  if (status & MCP960X_STATUS_ALERT1) { Serial.print("Alert 1, "); }
  if (status & MCP960X_STATUS_ALERT2) { Serial.print("Alert 2, "); }
  if (status & MCP960X_STATUS_ALERT3) { Serial.print("Alert 3, "); }
  if (status & MCP960X_STATUS_ALERT4) { Serial.print("Alert 4, "); }
  Serial.println();
  */

  //Serial.print("Th(degC),");
  Serial.print(mcp.readThermocouple());
  //Serial.print(",Tc(degC),");
  Serial.print(",");
  Serial.print(mcp.readAmbient());
  //Serial.print(",ADC(uV),");
  Serial.print(",");
  Serial.print(mcp.readADC() * 2);

  Serial.print("\n");

  i2cSendValue(int((mcp.readThermocouple()+0.05)*10), cycles); //Send the four characters to the display
  cycles++;

  delay(1000);
}

void i2cSendValue(int T_value, int cycles)
{
  Wire.beginTransmission(DISPLAY_ADDRESS1); // transmit to device #1

  Wire.write(0x7A); // Brightness control command
  Wire.write(50); // Set brightness level: 0% to 100%

  if (cycles % 2 == 0){
    // Wire.beginTransmission(DISPLAY_ADDRESS1); // transmit to device #1
    Wire.write(0x77); // Decimal control command
    Wire.write(0b00000100); // Turn on far-right decimal
    // Wire.endTransmission(); //Stop I2C transmission
  }
  if (cycles % 2 == 1){
    // Wire.beginTransmission(DISPLAY_ADDRESS1); // transmit to device #1
    Wire.write(0x77); // Decimal control command
    Wire.write(0b00100100); // Turn on far-right decimal
    // Wire.endTransmission(); //Stop I2C transmission
  }

  Wire.write(T_value / 1000); //Send the left most digit
  T_value %= 1000; //Now remove the left most digit from the number we want to display
  Wire.write(T_value / 100);
  T_value %= 100;
  Wire.write(T_value / 10);
  T_value %= 10;
  Wire.write(T_value); //Send the right most digit

  Wire.endTransmission(); //Stop I2C transmission
}
