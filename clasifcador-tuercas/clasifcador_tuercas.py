import cv2
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import numpy as np
import serial
import mysql.connector

class VentanaOperador:
    def __init__(self, root):
        self.root = root
        self.root.title("Registro de Operador")
        self.root.geometry("400x350")
        self.root.resizable(False, False)
        
        self.txt_nombre = tk.StringVar()
        self.cmb_sexo = tk.StringVar(value="Masculino")
        self.txt_edad = tk.StringVar()

        self.crear_formulario()

    def crear_formulario(self):
        ttk.Label(self.root, text="REGISTRO DE OPERADOR", font=("Arial", 14, "bold")).pack(pady=20)
        
        frame_form = ttk.Frame(self.root)
        frame_form.pack(pady=10, padx=20, fill="x")

        ttk.Label(frame_form, text="Nombre completo:", font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(frame_form, textvariable=self.txt_nombre, width=25).grid(row=0, column=1, pady=8)

        ttk.Label(frame_form, text="Sexo:", font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=8)
        combo_sexo = ttk.Combobox(frame_form, textvariable=self.cmb_sexo, values=["Masculino", "Femenino", "Otro"], width=23, state="readonly")
        combo_sexo.grid(row=1, column=1, pady=8)

        ttk.Label(frame_form, text="Edad:", font=("Arial", 10)).grid(row=2, column=0, sticky="w", pady=8)
        ttk.Entry(frame_form, textvariable=self.txt_edad, width=25).grid(row=2, column=1, pady=8)

        btn_entrar = ttk.Button(self.root, text="Iniciar Sistema", command=self.guardar_y_continuar)
        btn_entrar.pack(pady=20)

    def guardar_y_continuar(self):
        nombre = self.txt_nombre.get().strip()
        sexo = self.cmb_sexo.get().strip()
        edad_str = self.txt_edad.get().strip()

        if not nombre or not edad_str:
            messagebox.showerror("Error", "Por favor, complete todos los campos.")
            return

        try:
            edad = int(edad_str)
        except ValueError:
            messagebox.showerror("Error", "La edad debe ser un número entero.")
            return

        try:
            conexion = mysql.connector.connect(
                host="127.0.0.1",
                user="root",
                password="Davidpro#4659",
                database="clasificadora_tuercas"
            )
            cursor = conexion.cursor()

            sql = "INSERT INTO operador (nombre, sexo, edad, id_tipotuerca) VALUES (%s, %s, %s, %s)"
            cursor.execute(sql, (nombre, sexo, edad, 1))
            conexion.commit()
            
            cursor.close()
            conexion.close()
        except mysql.connector.Error as err:
            messagebox.showwarning("Aviso BD", f"No se pudo guardar el operador en la base de datos: {err}")

        self.root.destroy()
        ventana_principal = tk.Tk()
        ClasificadorTuercas(ventana_principal, nombre)
        ventana_principal.mainloop()


class ClasificadorTuercas:
    def __init__(self, ventana, operador_nombre):
        self.ventana = ventana
        self.operador_nombre = operador_nombre
        self.ventana.title(f"Clasificador de tuercas - Operador: {self.operador_nombre}")
        self.ventana.geometry("1150x850")
        self.ventana.minsize(900, 750)
        
        self.camara = None
        self.activo = False
        self.umbral = tk.IntVar(value=130)
        self.indice_camara = tk.IntVar(value=0)
        
        self.total_acumulado = 0
        self.hex_acumuladas = 0
        self.mar_acumuladas = 0
        self.rech_acumuladas = 0
        
        self.siguiente_id = 0
        self.centros_previos = {}
        self.piezas_contadas_ids = set()
        self.frames_vacio = 0
        
        try:
            self.arduino = serial.Serial('COM7', 9600, timeout=0.1)
        except Exception as e:
            self.arduino = None
            
        self.crear_interfaz()
        self.actualizar_tablas()

    def crear_interfaz(self):
        titulo = ttk.Label(self.ventana, text=f"CLASIFICADOR DE TUERCAS | Operador: {self.operador_nombre}", font=("Arial", 16, "bold"))
        titulo.pack(pady=5)
        
        controles = ttk.Frame(self.ventana)
        controles.pack(pady=2)
        
        ttk.Label(controles, text="Índice de cámara:").grid(row=0, column=0, padx=5)
        tk.Spinbox(controles, from_=0, to=5, width=5, textvariable=self.indice_camara).grid(row=0, column=1, padx=5)
        ttk.Button(controles, text="Iniciar cámara", command=self.iniciar_camara).grid(row=0, column=2, padx=5)
        ttk.Button(controles, text="Detener cámara", command=self.detener_camara).grid(row=0, column=3, padx=5)
        ttk.Button(controles, text="Parar Banda", command=self.parar_banda).grid(row=0, column=4, padx=5)
        
        ttk.Label(self.ventana, text="Umbral de detección").pack(pady=(2, 0))
        
        frame_umbral = ttk.Frame(self.ventana)
        frame_umbral.pack(pady=2)
        
        self.lbl_valor_umbral = ttk.Label(frame_umbral, text=f"Valor: {self.umbral.get()} / 255", font=("Arial", 10, "bold"))
        self.lbl_valor_umbral.pack(side="right", padx=10)
        
        ttk.Scale(frame_umbral, from_=0, to=255, variable=self.umbral, orient="horizontal", length=350, command=self.actualizar_etiqueta_umbral).pack(side="left")
        
        paneles = ttk.Frame(self.ventana)
        paneles.pack(fill="both", expand=True, padx=10, pady=5)
        
        panel_color = ttk.LabelFrame(paneles, text="Cámara a color y clasificación")
        panel_color.pack(side="left", fill="both", expand=True, padx=5)
        
        panel_mascara = ttk.LabelFrame(paneles, text="Máscara binaria procesada")
        panel_mascara.pack(side="left", fill="both", expand=True, padx=5)
        
        self.etiqueta_color = ttk.Label(panel_color)
        self.etiqueta_color.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.etiqueta_mascara = ttk.Label(panel_mascara)
        self.etiqueta_mascara.pack(fill="both", expand=True, padx=5, pady=5)

        frame_tablas = ttk.Frame(self.ventana)
        frame_tablas.pack(fill="both", expand=True, padx=10, pady=5)
        
        panel_hex = ttk.LabelFrame(frame_tablas, text="Registros Hexagonales")
        panel_hex.pack(side="left", fill="both", expand=True, padx=5)
        
        self.tabla_hex = ttk.Treeview(panel_hex, columns=("id", "marca", "tamano", "medida", "forma"), show="headings", height=4)
        self.tabla_hex.heading("id", text="ID")
        self.tabla_hex.heading("marca", text="Marca")
        self.tabla_hex.heading("tamano", text="Tamaño")
        self.tabla_hex.heading("medida", text="Medida")
        self.tabla_hex.heading("forma", text="Forma")
        self.tabla_hex.column("id", width=40)
        self.tabla_hex.pack(fill="both", expand=True, padx=5, pady=5)
        
        panel_mar = ttk.LabelFrame(frame_tablas, text="Registros Mariposa")
        panel_mar.pack(side="left", fill="both", expand=True, padx=5)
        
        self.tabla_mar = ttk.Treeview(panel_mar, columns=("id", "marca", "tamano", "medida", "forma"), show="headings", height=4)
        self.tabla_mar.heading("id", text="ID")
        self.tabla_mar.heading("marca", text="Marca")
        self.tabla_mar.heading("tamano", text="Tamaño")
        self.tabla_mar.heading("medida", text="Medida")
        self.tabla_mar.heading("forma", text="Forma")
        self.tabla_mar.column("id", width=40)
        self.tabla_mar.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.estado = ttk.Label(self.ventana, text="Cámara detenida", font=("Arial", 10))
        self.estado.pack(pady=2)
        
        self.contadores = ttk.Label(self.ventana, text="Total: 0 | Hexagonales: 0 | Mariposa: 0 | Rechazadas: 0", font=("Arial", 11, "bold"))
        self.contadores.pack(pady=5)
        
        self.ventana.protocol("WM_DELETE_WINDOW", self.cerrar_programa)

    def actualizar_etiqueta_umbral(self, valor):
        self.lbl_valor_umbral.config(text=f"Valor: {int(float(valor))} / 255")

    def iniciar_camara(self):
        if self.activo: return
        indice = self.indice_camara.get()
        self.camara = cv2.VideoCapture(indice, cv2.CAP_DSHOW)
        if not self.camara.isOpened():
            self.camara = cv2.VideoCapture(indice)
            if not self.camara.isOpened():
                self.estado.config(text=f"Error: No se pudo conectar a la cámara {indice}.")
                self.camara = None
                return
        self.activo = True
        self.estado.config(text=f"Cámara USB {indice} conectada")
        self.actualizar_video()

    def detener_camara(self):
        self.activo = False
        if self.camara is not None:
            self.camara.release()
            self.camara = None
        self.estado.config(text="Cámara detenida")

    def parar_banda(self):
        if self.arduino is not None:
            self.arduino.write(b'4')
        self.estado.config(text="Banda detenida manualmente desde el software")

    def actualizar_video(self):
        if not self.activo or self.camara is None: return
        correcto, frame = self.camara.read()
        if not correcto:
            self.estado.config(text="No se pudo leer la imagen")
            self.ventana.after(100, self.actualizar_video)
            return

        mascara = self.procesar_imagen(frame)
        imagen_resultado = frame.copy()
        imagen_resultado = self.clasificar_piezas(mascara, imagen_resultado)

        self.mostrar_imagen(imagen_resultado, self.etiqueta_color, "color")
        self.mostrar_imagen(mascara, self.etiqueta_mascara, "mascara")
        self.ventana.after(15, self.actualizar_video)

    def procesar_imagen(self, frame):
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        desenfoque = cv2.medianBlur(gris, 13)
        desenfoque = cv2.GaussianBlur(desenfoque, (5, 5), 0)
        _, mascara = cv2.threshold(desenfoque, self.umbral.get(), 255, cv2.THRESH_BINARY)
        
        kernel = np.ones((9, 9), np.uint8)
        kernel_suavizado = np.ones((15, 15), np.uint8)
        
        mascara = cv2.erode(mascara, kernel, iterations=2)
        mascara = cv2.dilate(mascara, kernel, iterations=2)
        mascara = cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, kernel_suavizado)
        return mascara

    def conectar_bd(self):
        return mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="Davidpro#4659",
            database="clasificadora_tuercas"
        )

    def actualizar_tablas(self):
        try:
            conexion = self.conectar_bd()
            cursor = conexion.cursor()
            cursor.execute("SELECT * FROM hexagonal")
            filas_hex = cursor.fetchall()
            cursor.execute("SELECT * FROM mariposa")
            filas_mar = cursor.fetchall()
            cursor.close()
            conexion.close()
            
            self.tabla_hex.delete(*self.tabla_hex.get_children())
            for fila in filas_hex:
                self.tabla_hex.insert("", "end", values=fila)
                
            self.tabla_mar.delete(*self.tabla_mar.get_children())
            for fila in filas_mar:
                self.tabla_mar.insert("", "end", values=fila)
        except mysql.connector.Error as err:
            pass

    def registrar_en_mysql(self, categoria):
        try:
            conexion = self.conectar_bd()
            cursor = conexion.cursor()
            
            if categoria == "HEXAGONAL":
                sql_tipo = "UPDATE tipo_tuerca SET conteo = conteo + 1 WHERE id_tipotuerca = 1"
                cursor.execute(sql_tipo)
                conexion.commit()
                
                sql_hex = "INSERT INTO hexagonal (marca, tamano, medida, forma, id_tipotuerca) VALUES ('Estandar', '3/4', '10mm', 'Hexagonal', 1)"
                cursor.execute(sql_hex)
                conexion.commit()
                
            elif categoria == "MARIPOSA":
                sql_tipo = "UPDATE tipo_tuerca SET conteo = conteo + 1 WHERE id_tipotuerca = 2"
                cursor.execute(sql_tipo)
                conexion.commit()
                
                sql_mar = "INSERT INTO mariposa (marca, tamano, medida, forma, id_tipotuerca) VALUES ('Estandar', '1/4', '8mm', 'Mariposa', 2)"
                cursor.execute(sql_mar)
                conexion.commit()
                
            cursor.close()
            conexion.close()
            self.actualizar_tablas()
        except mysql.connector.Error as err:
            pass

    def clasificar_piezas(self, mascara, imagen):
        contornos, jerarquia = cv2.findContours(mascara, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        alto, ancho = mascara.shape
        
        zona_izq = int(ancho * 0.125)
        zona_der = int(ancho * 0.875)
        cv2.line(imagen, (zona_izq, 0), (zona_izq, alto), (0, 255, 255), 2)
        cv2.line(imagen, (zona_der, 0), (zona_der, alto), (0, 255, 255), 2)
        cv2.putText(imagen, "ZONA DE CONTEO (3/4)", (zona_izq + 10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        centros_actuales = []

        if jerarquia is None:
            self.frames_vacio += 1
            if self.frames_vacio > 20:
                self.piezas_contadas_ids.clear()
                self.centros_previos.clear()
            return imagen

        self.frames_vacio = 0
        jerarquia = jerarquia[0]
        area_minima = 7000
        area_maxima = 60000

        for i, contorno in enumerate(contornos):
            if jerarquia[i][3] != -1: continue
            
            area = cv2.contourArea(contorno)
            if area < area_minima or area > area_maxima: continue

            x, y, w, h = cv2.boundingRect(contorno)
            cx = x + (w // 2)
            cy = y + (h // 2)

            margen = 20
            if x < margen or (x + w) > (ancho - margen) or y < margen or (y + h) > (alto - margen):
                continue

            envolvente = cv2.convexHull(contorno)
            area_envolvente = cv2.contourArea(envolvente)
            if area_envolvente == 0: continue

            solidez = float(area) / area_envolvente
            relacion_aspecto = float(w) / h

            agujeros = []
            hijo = jerarquia[i][2]
            while hijo != -1:
                area_agujero = cv2.contourArea(contornos[hijo])
                if area_agujero >= max(50, area * 0.02) and area_agujero <= area * 0.35:
                    agujeros.append(hijo)
                hijo = jerarquia[hijo][0]

            tiene_agujero = len(agujeros) > 0

            if tiene_agujero:
                if solidez >= 0.80 and 0.6 <= relacion_aspecto <= 1.4:
                    categoria = "HEXAGONAL"
                    color = (255, 0, 0)
                elif 0.30 <= solidez < 0.80:
                    categoria = "MARIPOSA"
                    color = (0, 255, 0)
                else:
                    categoria = "RECHAZADO"
                    color = (0, 0, 255)
            else:
                categoria = "RECHAZADO"
                color = (0, 0, 255)

            centros_actuales.append({
                'cx': cx, 'cy': cy, 'categoria': categoria, 'color': color, 
                'tiene_agujero': tiene_agujero, 'contorno': contorno, 'agujeros': agujeros,
                'x': x, 'y': y
            })

        nuevos_centros_rastreados = {}
        ids_usados_este_frame = set()

        for pieza in centros_actuales:
            cx, cy = pieza['cx'], pieza['cy']
            pieza_match_id = None
            distancia_minima = 80

            for p_id, (px, py) in self.centros_previos.items():
                if p_id in ids_usados_este_frame: continue
                distancia = ((cx - px)**2 + (cy - py)**2)**0.5
                if distancia < distancia_minima:
                    distancia_minima = distancia
                    pieza_match_id = p_id

            if pieza_match_id is not None:
                nuevos_centros_rastreados[pieza_match_id] = (cx, cy)
                ids_usados_este_frame.add(pieza_match_id)
            else:
                nuevos_centros_rastreados[self.siguiente_id] = (cx, cy)
                pieza_match_id = self.siguiente_id
                self.siguiente_id += 1

            if zona_izq < cx < zona_der:
                if pieza_match_id not in self.piezas_contadas_ids:
                    if pieza['categoria'] == "HEXAGONAL": 
                        self.hex_acumuladas += 1
                        self.registrar_en_mysql("HEXAGONAL")
                        if self.arduino is not None:
                            self.arduino.write(b'1')
                    elif pieza['categoria'] == "MARIPOSA": 
                        self.mar_acumuladas += 1
                        self.registrar_en_mysql("MARIPOSA")
                        if self.arduino is not None:
                            self.arduino.write(b'3')
                    else: 
                        self.rech_acumuladas += 1
                        if self.arduino is not None:
                            self.arduino.write(b'0')
                    
                    self.total_acumulado += 1
                    self.piezas_contadas_ids.add(pieza_match_id) 

            cv2.drawContours(imagen, [pieza['contorno']], -1, pieza['color'], 3)
            for idx_agujero in pieza['agujeros']:
                cv2.drawContours(imagen, [contornos[idx_agujero]], -1, (0, 255, 255), 2)
            
            texto = f"ID:{pieza_match_id} {pieza['categoria']}" + (" (OK)" if pieza['tiene_agujero'] else " (SIN)")
            cv2.putText(imagen, texto, (pieza['x'], max(pieza['y'] - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, pieza['color'], 2, cv2.LINE_AA)

        self.centros_previos = nuevos_centros_rastreados

        self.actualizar_contadores()
        return imagen

    def actualizar_contadores(self):
        self.contadores.config(
            text=f"Total Acumulado: {self.total_acumulado} | Hexagonales: {self.hex_acumuladas} | Mariposa: {self.mar_acumuladas} | Rechazadas: {self.rech_acumuladas}"
        )

    def mostrar_imagen(self, imagen, etiqueta, tipo):
        if len(imagen.shape) == 2: imagen_pil = Image.fromarray(imagen)
        else: imagen_pil = Image.fromarray(cv2.cvtColor(imagen, cv2.COLOR_BGR2RGB))
        imagen_pil.thumbnail((520, 420), Image.Resampling.LANCZOS)
        imagen_tk = ImageTk.PhotoImage(imagen_pil)
        if tipo == "color": self.imagen_color_tk = imagen_tk
        else: self.imagen_mascara_tk = imagen_tk
        etiqueta.config(image=imagen_tk)

    def cerrar_programa(self):
        self.detener_camara()
        if self.arduino is not None: self.arduino.close()
        self.ventana.destroy()

if __name__ == "__main__":
    ventana_login = tk.Tk()
    app_login = VentanaOperador(ventana_login)
    ventana_login.mainloop()