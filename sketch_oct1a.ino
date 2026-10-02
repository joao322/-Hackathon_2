
// CONTROLE DE LÂMPADA PELO RELÉ


const int RELE = 7;

void setup() {

  pinMode(RELE, OUTPUT);

  // Começa com a lâmpada desligada
  digitalWrite(RELE, HIGH);

  // Comunicação com o Python
  Serial.begin(9600);
}

void loop() {

  // Recebe comando do computador
  if (Serial.available() > 0) {

    char comando = Serial.read();

    // Ligar lâmpada
    if (comando == 'L') {
      digitalWrite(RELE, LOW);
    }

    // Desligar lâmpada
    if (comando == 'D') {
      digitalWrite(RELE, HIGH);
    }
  }
}
