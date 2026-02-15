"""
Script de obra Donante Universal
Sincroniza la bomba con el nivel del tanque septico de la ISS en tiempo real
"""

import RPi.GPIO as GPIO
import time
import random
from datetime import datetime, timedelta

try:
    from lightstreamer.client import LightstreamerClient, Subscription, SubscriptionListener
    LIGHTSTREAMER_DISPONIBLE = True
except ImportError:
    LIGHTSTREAMER_DISPONIBLE = False
    print("[!] lightstreamer-client-lib no esta instaladoooo")

# configuracion GPIO
PIN_IN1 = 17
PIN_IN2 = 27
PIN_ENA = 22

# Lightstreamer
SERVIDOR_LS = "push.lightstreamer.com"
ADAPTADOR_LS = "ISSLIVE"
ITEM_LS = "NODE3000005"

# sys conexion 
INTENTOS_MAXIMOS_CONEXION = 5
TIMEOUT_CONEXION = 15  # timeout conexión
TIMEOUT_SIN_DATOS = 120  # segundos para timeout
INTERVALO_RECONEXION_INICIAL = 5  # segundos
INTERVALO_RECONEXION_MAXIMO = 60  # segundos (backoff exponencial)

# globales
nivel_actual = 0
pwm = None
ejecutando = True
ultima_actualizacion = None
modo_actual = "inicializando"  # estados: inicializando - conectado - simulacion


if LIGHTSTREAMER_DISPONIBLE:
    class EscuchadorDatosISS(SubscriptionListener):
        """recive y procesa actualizaciones de datos de la ISS"""
        
        def __init__(self, funcion_callback):
            self.funcion_callback = funcion_callback
            self.contador_actualizaciones = 0

        def onItemUpdate(self, update):
            global ultima_actualizacion
            try:
                valor = float(update.getValue("Value")) if update.getValue("Value") else None
                if valor is not None:
                    ultima_actualizacion = datetime.now()
                    self.contador_actualizaciones += 1
                    self.funcion_callback(valor)
            except (ValueError, TypeError) as e:
                print(f"[ls] error procesando valor: {e}")

        def onSubscription(self):
            print("[ls] suscripcion activa, esperando datos")

        def onSubscriptionError(self, code, message):
            print(f"[ls] error suscripcion {code}: {message}")

        def onUnsubscription(self):
            print("[ls] suscripcion cancelada")


    class ClienteLS:
        """cliente conexión con Lightstreamer"""
        
        def __init__(self, servidor, adaptador):
            self.cliente = LightstreamerClient(f"https://{servidor}", adaptador)
            self.suscripcion = None
            self.conectado = False
            self.escuchador = None
            self.cliente.connectionOptions.setConnectTimeout(TIMEOUT_CONEXION)
            self.cliente.connectionOptions.setCurrentConnectTimeout(TIMEOUT_CONEXION)
            self.cliente.connectionOptions.setRetryDelay(1000)

        def conectar(self):
            """busca conexión con el servidor con timeout"""
            try:
                print("[ls] intentando conectar...")
                self.cliente.connect()
                
                # busca confirmacion conexion
                tiempo_inicio = time.time()
                while time.time() - tiempo_inicio < TIMEOUT_CONEXION:
                    if self.cliente.getStatus() == "CONNECTED:STREAM-SENSING":
                        self.conectado = True
                        print("[ls] conectado")
                        return True
                    time.sleep(0.5)
                
                print("[ls] timeout esperando conexion")
                return False
                
            except Exception as e:
                print(f"[ls] error de conexion: {e}")
                self.conectado = False
                return False

        def esta_conectado(self):
            """Verifica si la conexión está activa"""
            if not self.conectado:
                return False
            
            estado = self.cliente.getStatus()
            return estado in ["CONNECTED:STREAM-SENSING", "CONNECTED:WS-STREAMING"]

        def suscribir(self, item, campo, funcion_callback):
            """suscribe a un item específico y procesa actualizaciones"""
            global ultima_actualizacion, modo_actual
            
            self.suscripcion = Subscription("MERGE", [item], [campo])
            self.suscripcion.setRequestedSnapshot("yes")
            self.escuchador = EscuchadorDatosISS(funcion_callback)
            self.suscripcion.addListener(self.escuchador)
            self.cliente.subscribe(self.suscripcion)
            
            ultima_actualizacion = datetime.now()
            modo_actual = "conectado"
            print(f"[ls] suscrito a {item}, esperando actualizaciones...")
            
            # monitorear conexion y datos
            ultima_verificacion = time.time()
            while ejecutando:
                time.sleep(1)
                
                # verificar estado conexion > X segundos
                if time.time() - ultima_verificacion > 5:
                    ultima_verificacion = time.time()
                    
                    if not self.esta_conectado():
                        print("[ls] conexion perdida")
                        return False
                    
                    # verificar si se reciben datos recientemente
                    if ultima_actualizacion:
                        tiempo_sin_datos = (datetime.now() - ultima_actualizacion).total_seconds()
                        if tiempo_sin_datos > TIMEOUT_SIN_DATOS:
                            print(f"[ls] sin datos por {tiempo_sin_datos:.0f}s, posible problemaaaa")
                            return False
                        elif tiempo_sin_datos > 30:
                            # advertencia pero no es critico
                            if int(tiempo_sin_datos) % 30 == 0:
                                print(f"[ls] ultima actualizacion hace {tiempo_sin_datos:.0f}s")
            
            return True

        def desconectar(self):
            """cierra conexión y cancela suscripciones"""
            try:
                if self.suscripcion:
                    self.cliente.unsubscribe(self.suscripcion)
                self.cliente.disconnect()
                self.conectado = False
                print("[ls] desconectado")
            except Exception as e:
                print(f"[ls] error al desconectar: {e}")
else:
    class ClienteLS:
        def __init__(self, *_):
            raise ImportError("lightstreamer-client-lib no disponible")


def configurar_gpio():
    """configura GPIO para controlar bomba"""
    global pwm
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(PIN_IN1, GPIO.OUT)
    GPIO.setup(PIN_IN2, GPIO.OUT)
    GPIO.setup(PIN_ENA, GPIO.OUT)
    pwm = GPIO.PWM(PIN_ENA, 1000)
    pwm.start(0)
    print("[gpio] configuracion ok")


def ajustar_velocidad_bomba(nivel: float) -> float:
    """
    ajusta la velocidad de la bomba según el nivel del tanque
    """
    nivel = max(0, min(100, nivel))
    
    if nivel < 5:
        GPIO.output(PIN_IN1, GPIO.LOW)
        GPIO.output(PIN_IN2, GPIO.LOW)
        pwm.ChangeDutyCycle(0)
        return 0
    
    # locura para que la bomba funcione
    velocidad = 50 + ((nivel - 5) * 50 / 95)
    GPIO.output(PIN_IN1, GPIO.HIGH)
    GPIO.output(PIN_IN2, GPIO.LOW)
    pwm.ChangeDutyCycle(velocidad)
    return velocidad


def actualizar_tanque(nivel: float):
    """
    callback que se ejecuta cuando se recibe una actualización del nivel
    """
    global nivel_actual
    nivel_actual = nivel
    velocidad_actual = ajustar_velocidad_bomba(nivel)
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{modo_actual.upper()}] Nivel {nivel:.1f}% | Bomba {velocidad_actual:.0f}% PWM")


def simular_tanque():
    """
    simula cambios en el nivel del tanque basados en patrones de la ISS - porsiaca no hay wifi
    """
    global modo_actual
    modo_actual = "simulacion"
    
    print("[sim] modo wifin't activado")
    print("[sim] simulando conexion con la iss")
    
    # estado inicial aleatorio
    nivel = random.uniform(30, 60)
    velocidad_llenado = random.uniform(0.2, 0.5)  # % por ciclo 
    tiempo_hasta_vaciado = random.randint(100, 200)
    ciclos = 0
    
    while ejecutando:
        ciclos += 1
        
        # fase de llenado gradual (uso normal del estanque)
        if ciclos < tiempo_hasta_vaciado:
            # llenado gradual con variaciones
            nivel += velocidad_llenado + random.uniform(-0.1, 0.2)
            
            # eventos aleatorios (jeje)
            if random.random() < 0.05:  # probar 5% de probabilidad
                nivel += random.uniform(1, 3)
                print("[sim] evento baño rng")
            
            # limitar el nivel al maximo operativo
            nivel = min(85, nivel)
        
        # fase de donacion universal (vaciado)
        else:
            print("[sim] iniciando secuencia de vaciado")
            while nivel > 15 and ejecutando:
                nivel -= random.uniform(2, 5)
                nivel = max(15, nivel)
                actualizar_tanque(nivel)
                time.sleep(1)
            
            # restet nuevo ciclo
            print("[sim] vaciado completado, nuevo ciclo")
            tiempo_hasta_vaciado = random.randint(100, 200)
            velocidad_llenado = random.uniform(0.2, 0.5)
            ciclos = 0
        
        # fluctuaciones para darle dinamismo
        nivel += random.uniform(-0.3, 0.3)
        nivel = max(15, min(85, nivel))
        
        actualizar_tanque(nivel)
        time.sleep(2)


def intentar_conexion_con_reintentos():
    """
    intenta conectar al servidor con reintentos y backoff exponencial para que no quickeen la conexion
    """
    intervalo_actual = INTERVALO_RECONEXION_INICIAL
    
    for intento in range(1, INTENTOS_MAXIMOS_CONEXION + 1):
        print(f"\n[sys] intento de conexion {intento}/{INTENTOS_MAXIMOS_CONEXION}")
        
        try:
            cliente = ClienteLS(SERVIDOR_LS, ADAPTADOR_LS)
            if cliente.conectar():
                print("[sys] conexion establecida")
                return cliente
        except Exception as e:
            print(f"[sys] error en intento {intento}: {e}")
        
        # si no es el ultimo intento, esperar con backoff exponencial
        if intento < INTENTOS_MAXIMOS_CONEXION:
            print(f"[sys] esperando {intervalo_actual}s antes del proximo intento...")
            time.sleep(intervalo_actual)
            intervalo_actual = min(intervalo_actual * 2, INTERVALO_RECONEXION_MAXIMO)
    
    print("[sys] todos los intentos de conexion fallaron lol")
    return None


def limpiar_gpio():
    """apaga la bomba y limpia la configuracion GPIO"""
    print("[sys] apagando bomba y limpiando gpio")
    GPIO.output(PIN_IN1, GPIO.LOW)
    GPIO.output(PIN_IN2, GPIO.LOW)
    if pwm:
        pwm.stop()
    GPIO.cleanup()


def main():
    """funcion principal, reconexion automatica y simulacion x si no hay wifi"""
    global ejecutando, modo_actual
    
    print("donante universal V1.0.6")

    configurar_gpio()

    # si lightstreamer (o el wifi) no esta disponible, comenzar el modo simulacion para salvar 
    if not LIGHTSTREAMER_DISPONIBLE:
        print("\n[sys] biblioteca lightstreamer no disponible")
        print("[sys] modo simulacion permanente activado")
        try:
            simular_tanque()
        except KeyboardInterrupt:
            print("\n[sys] interrupcion detectada")
        finally:
            ejecutando = False
            limpiar_gpio()
        return

    # loop principal con reconexion automatica
    while ejecutando:
        cliente = None
        try:
            # intentar conectar con reintentos
            cliente = intentar_conexion_con_reintentos()
            
            if cliente:
                print(f"[sys] suscribiendo a {ITEM_LS}")
                conexion_exitosa = cliente.suscribir(ITEM_LS, "Value", actualizar_tanque)
                
                if not conexion_exitosa and ejecutando:
                    print("[sys] conexion interrumpida, intentando reconectar...")
                    time.sleep(5)
                    continue
            else:
                # si ya fallo la conexion, comenzar simulacion
                print("\n[sys] no se pudo establecer conexion")
                print("[sys] cambiando a modo simulacion")
                simular_tanque()
                break
                
        except KeyboardInterrupt:
            print("\n[sys] interrupcion detectada por usuario")
            break
            
        except Exception as e:
            print(f"\n[sys] error inesperado: {e}")
            print("[sys] reintentando en 10 segundos...")
            time.sleep(10)
            
        finally:
            if cliente:
                try:
                    cliente.desconectar()
                except Exception:
                    pass
    
    # limpieza final por si acaso
    ejecutando = False
    limpiar_gpio()
    print("\n[sys] programa finalizado")


if __name__ == "__main__":
    main()
