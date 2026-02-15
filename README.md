<p align="center">
  <img src="img/DonanteUniversal.avif" alt="Donante Universal" width="600">
</p>

# Donante Universal

<br/>

## Overview

**Donante Universal** es una obra que se activa a partir de la sincronización en tiempo real entre su propia bomba de agua y el tanque séptico de la Estación Espacial Internacional (ISS). 

## Funcionamiento

La obra se conecta a la API Lightstreamer de NASA para recibir actualizaciones del porcentaje del tanque séptico (item `NODE3000005`) y traduce estos datos en parámetros de control de su bomba de agua.

### Modo de Simulación

Si la conexión a la NASA (o el wifi) no está disponible, el sistema activa automáticamente un modo de simulación que reproduce los patrones operativos de la ISS.

## Componentes

### Hardware
- Raspberry Pi 4B
- Driver motor L298N
- Bomba de agua DC 12V

### Software
- Python 3.7+
- Bibliotecas requeridas:
  - `RPi.GPIO`
  - `lightstreamer-client-lib`