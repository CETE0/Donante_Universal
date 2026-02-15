```markdown
# Donante Universal

Obra con sincronización en tiempo real entre su bomba de agua y el tanque séptico de la ISS.

## Funcionamiento

La obra se conecta a la API Lightstreamer de NASA para recibir actualizaciones del porcentaje del tanque séptico (item NODE3000005). El sistema traduce estos datos en dos parámetros de control: velocidad, que se mapea linealmente del 50% al 100% según el nivel del tanque, y frecuencia PWM, que varía entre 100 Hz y 1500 Hz alterando el ritmo de pulsación.

Si la conexión a la NASA (o el wifi) no está disponible, el sistema activa automáticamente un modo de simulación que reproduce los patrones operativos de la ISS.

## Componentes

El hardware consiste en una Raspberry Pi 4B, un driver motor L298N, una bomba de agua DC 12V. El software requiere Python 3.7+ con las bibliotecas RPi.GPIO y lightstreamer-client-lib.# Donante_Universal
