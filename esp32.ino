#include <WiFi.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_HMC5883_U.h>
#include <string>
#include <SkinConductance.h>
#include <Heart.h>
#include <Respiration.h>
#include <ArduinoJson.h>

/* Assign a unique ID to this sensor at the same time */
Adafruit_HMC5883_Unified mag = Adafruit_HMC5883_Unified(12345);
/* Put your SSID & Password */
const char* ssid = "Jagadish Sahu";  // Enter SSID here
const char* password = "pr0ffapt@m1fi";  //Enter Password here
const int capacity = JSON_OBJECT_SIZE(11);
SkinConductance sc(A6);
Heart hrt(A6);
Respiration resp(A6);
int avgBPM=0;
int bpmCounter = 0;      // counter for counting bpmArray position     
int bpmArray[100];   // the array that holds bpm values. Define as a large number you don't need to use them all.
int totalBPM = 0;          // value for displaying average BPM over several heartbeats
int arraySize = 5;   //determine how many beats you will collect and average

unsigned long litMillis = 0;        // will store how long LED was lit up
// if you do not receive a heartbeat value in over 5 seconds, flush the BPM array and start fresh
const long flushInterval = 2000;    //interval at which to refresh values stored in array
boolean doOnce = true;   // makes sure that if a heartbeat is found that information is gathered only once during cycle


WebServer server(80);

String get_sensor_details(void)
{
  sensor_t sensor;
  mag.getSensor(&sensor);

  DynamicJsonDocument doc(capacity);
  JsonObject mag = doc.createNestedObject("mag");
  
  String res;
  mag["Sensor"] = sensor.name ;
  mag["Driver Ver"] = sensor.version;
  mag["Unique ID"] = sensor.sensor_id;
  mag["Max Value"] = String(sensor.max_value) + " uT";
  mag["Min Value"] = String(sensor.min_value) + " uT";
  mag["Resolution"]= String(sensor.resolution) + " uT";  

  serializeJson(doc, res);  

  return res;
}


void setup(void) 
{
  Serial.begin(9600);
  sc.reset();
  hrt.reset();
  resp.reset();

  /* Initialise the sensor */
  if(!mag.begin())
  {
    /* There was a problem detecting the HMC5883 ... check your connections */
    Serial.println("Ooops, no HMC5883 detected ... Check your wiring!");
    while(1);
  }

  Serial.print("Connecting to ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  // Print local IP address and start web server
  Serial.println("");
  Serial.println("WiFi connected.");
  Serial.println("IP address: ");
  Serial.println(WiFi.localIP());
  delay(1000);
  
  server.on("/", handle_OnConnect);
  server.on("/get_sensor_details", handle_get_sensor_details);
  server.on("/get_all_data", handle_get_all_data);
  server.on("/get_mag_data", handle_get_mag_data);
  server.on("/get_gsr_data", handle_get_gsr_data);
  server.onNotFound(handle_NotFound);
  
  server.begin();
  Serial.println("HTTP server started");
  
  /* Display some basic information on this sensor */
  Serial.println(get_sensor_details());
}

  sensors_event_t event; 


void loop(void) 
{
  /* Get a new sensor event */ 
  mag.getEvent(&event);
  server.handleClient();
  sc.update();
  hrt.update();
  resp.update();

  unsigned long currentMillis = millis();   


  if (hrt.beatDetected()){  
    if (doOnce == true){
    litMillis = currentMillis;    
    bpmArray[bpmCounter] = hrt.getBPM();  // grab a BPM snapshot every time a heartbeat occurs
    bpmCounter++;                           // increment the BPMcounter value
    doOnce = false;
    }
  }
  else {
    doOnce = true;
  }

  if (bpmCounter == (arraySize)) {                    // if you have grabbed enough heartbeats to average                                      
    
    for (int x = 0; x <= (arraySize-1); x++) {          // add up all the values in the array
      totalBPM = totalBPM + bpmArray[x];
    }

    avgBPM = totalBPM/arraySize;                 // divide by amount of values processed in array
    
    bpmCounter = 0;                     //  reset bpmCounter
    totalBPM = 0;                       // refresh totalBPM
    avgBPM = 0;                        // refresh avgBPM
    delay(2000);
  }
  // Serial.print("Your average BPM over ");
  //   Serial.print(arraySize);
  //   Serial.print(" beats is ");
  //   Serial.println(avgBPM);
  // check to see if it's time to turn off the LED

  if (currentMillis - litMillis >= flushInterval){  // if you haven't received a heartbeat in a while keep the array fresh
    bpmCounter = 0;
  }


}

void handle_OnConnect() {
  server.send(200, "text/html", get_main_page()); 
}

JsonDocument get_mag_data(){
  DynamicJsonDocument res_mag_data(capacity);
  /* Get a new sensor event */ 
  res_mag_data["sensor"] = "5883_GY-271";

  JsonObject data = res_mag_data.createNestedObject("data");

  data["X"] = event.magnetic.x;
  data["Y"] = event.magnetic.y;
  data["Z"] = event.magnetic.z;
  res_mag_data["Unit"] = "uT";

  // Hold the module so that Z is pointing 'up' and you can measure the heading with x&y
  // Calculate heading when the magnetometer is level, then correct for signs of axis.
  float heading = atan2(event.magnetic.y, event.magnetic.x);
  
  // Once you have your heading, you must then add your 'Declination Angle', which is the 'Error' of the magnetic field in your location.
  // Find yours here: http://www.magnetic-declination.com/
  // Mine is: -13* 2' W, which is ~13 Degrees, or (which we need) 0.22 radians
  // If you cannot find your Declination, comment out these two lines, your compass will be slightly off.
  float declinationAngle = 0.22;
  heading += declinationAngle;
  
  // Correct for when signs are reversed.
  if(heading < 0)
    heading += 2*PI;
    
  // Check for wrap due to addition of declination.
  if(heading > 2*PI)
    heading -= 2*PI;
   
  // Convert radians to degrees for readability.
  float headingDegrees = heading * 180/M_PI; 
  
  data["Heading (degrees)"] = headingDegrees;

  return res_mag_data;

}

void handle_get_mag_data() {
  String res;
  serializeJson(get_mag_data(), res);
  send_json_data(res);
}

JsonDocument get_gsr_data() {
  DynamicJsonDocument res_gsr_data(capacity);
  /* Get a new sensor event */ 
  JsonObject data = res_gsr_data.createNestedObject("data");
  res_gsr_data["sensor"] = "Groove GSR V1.2";

  JsonObject scdata = data.createNestedObject("SkinConductance"); 
  scdata["SCL"] = sc.getSCL();
  scdata["SCR"] = sc.getSCR();
  scdata["RAW"] = sc.getRaw();

  JsonObject hrtdata = data.createNestedObject("HeartBeat"); 
  hrtdata["BPM"] = hrt.getBPM();
  hrtdata["AVG_BPM"] = avgBPM;
  hrtdata["normalisedRAW"] = hrt.getNormalized();
  hrtdata["deltaBPM"] = hrt.bpmChange();
  hrtdata["deltaAMPLITUDE"] = hrt.amplitudeChange();

  JsonObject respdata = data.createNestedObject("Respiration"); 
  respdata["BPM"] = resp.getBPM();
  respdata["normalisedRAW"] = resp.getNormalized();
  respdata["deltaBPM"] = resp.bpmChange();
  respdata["deltaAMPLITUDE"] = resp.amplitudeChange();

  return res_gsr_data;
}

void handle_get_gsr_data() {
  String res;
  serializeJson(get_gsr_data(), res);
  send_json_data(res);
}

void handle_get_all_data() {
  DynamicJsonDocument res_all(capacity);

  res_all["mag"] = get_mag_data();
  res_all["gsr"] = get_gsr_data();
  String res;
  serializeJson(res_all, res);
  send_json_data(res);
}

void handle_get_sensor_details() {
  send_json_data(get_sensor_details().c_str());
}

void handle_NotFound(){
  server.send(404, "text/plain", "Not found");
}

void send_text(String response){
  server.send(200, "text/plain", response);
}

void send_json_data(String response){
  server.send(200, "application/json", response);
}

String get_main_page(){
  String ptr = "<!DOCTYPE html> <html>\n";
  ptr +="<head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0, user-scalable=no\">\n";
  ptr +="<title>LED Control</title>\n";
  ptr +="<style>html { font-family: Helvetica; display: inline-block; margin: 0px auto; text-align: center;}\n";
  ptr +="body{margin-top: 50px;} h1 {color: #444444;margin: 50px auto 30px;} h3 {color: #444444;margin-bottom: 50px;}\n";
  ptr +=".button {display: block;width: 80px;background-color: #3498db;border: none;color: white;padding: 13px 30px;text-decoration: none;font-size: 25px;margin: 0px auto 35px;cursor: pointer;border-radius: 4px;}\n";
  ptr +=".button-on {background-color: #3498db;}\n";
  ptr +=".button-on:active {background-color: #2980b9;}\n";
  ptr +=".button-off {background-color: #34495e;}\n";
  ptr +=".button-off:active {background-color: #2c3e50;}\n";
  ptr +="p {font-size: 14px;color: #888;margin-bottom: 10px;}\n";
  ptr +="</style>\n";
  ptr +="</head>\n";
  ptr +="<body>\n";
  ptr +="<h1>ESP32 Web Server</h1>\n";
  
  {ptr +="<p>Get All Data</p><a class=\"button button-on\" href=\"/get_all_data\">All Data</a>\n";}
  {ptr +="<p>Get Mag Data </p><a class=\"button button-on\" href=\"/get_mag_data\">Mag Data</a>\n";}
  {ptr +="<p>Get GSR Data</p><a class=\"button button-on\" href=\"/get_gsr_data\">GSR Data</a>\n";}
  {ptr +="<p>Get Sensor Details</p><a class=\"button button-on\" href=\"/get_sensor_details\">Sensor Details</a>\n";}

  ptr +="</body>\n";
  ptr +="</html>\n";
  return ptr;
}
