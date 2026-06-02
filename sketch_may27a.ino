const int R=8, Y=9, G=10, B_RST=2, B_REC=3;
bool blink=false, yState=false;
unsigned long lastBlink=0, lastBtn=0;

void setTL(char c) { digitalWrite(R,c=='R'); digitalWrite(Y,c=='Y'); digitalWrite(G,c=='G'); }
void blinkOn() { blink=true; yState=true; digitalWrite(Y,HIGH); digitalWrite(R,LOW); digitalWrite(G,LOW); }
void blinkOff() { blink=false; digitalWrite(R,LOW); digitalWrite(Y,LOW); digitalWrite(G,LOW); }

void setup() {
  Serial.begin(9600);
  pinMode(R,OUTPUT); pinMode(Y,OUTPUT); pinMode(G,OUTPUT);
  pinMode(B_RST,INPUT_PULLUP); pinMode(B_REC,INPUT_PULLUP);
}

void loop() {
  if(Serial.available()){
    char c=Serial.read();
    if(c=='B') blinkOn();
    else if(c=='K') blinkOff();
    else if(!blink && (c=='R'||c=='Y'||c=='G')) setTL(c);
  }
  unsigned long now=millis();
  if(now-lastBtn>200){
    if(digitalRead(B_RST)==LOW){ lastBtn=now; blinkOn(); Serial.write('F'); }
    else if(digitalRead(B_REC)==LOW){ lastBtn=now; blinkOff(); Serial.write('E'); }
  }
  if(blink && now-lastBlink>=500){
    lastBlink=now;
    yState=!yState;
    digitalWrite(Y,yState?HIGH:LOW);
  }
}