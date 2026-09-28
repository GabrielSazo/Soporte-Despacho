# Manual de usuario — Soporte Despacho Tigo | Centro de control

## 1. Ingreso al sistema
1. Abra la dirección que le indicó su administrador.
2. Ingrese su **correo institucional** y **contraseña** → **Ingresar al centro de control**.
3. Si es su primer ingreso (cuenta creada por carga masiva o por un administrador), abra el correo de bienvenida y pulse **Definir mi contraseña** (válido 1 hora). Su clave debe tener mínimo 10 caracteres, una mayúscula, una minúscula y un número; la pantalla le marca cada requisito.
4. ¿Olvidó su clave? Pulse **¿Olvidaste tu contraseña?**, ingrese su correo y siga el enlace recibido.
5. Tras **5 intentos fallidos** la cuenta se bloquea y solo se desbloquea definiendo una nueva clave por correo.

## 2. Pantalla principal
- **Menú lateral:** Resumen, Tickets, Validaciones, Escalados, Mi grupo, Informes (según su rol) y Administración (solo administradores y supervisores).
- **Campana:** notificaciones (validaciones, asignaciones, escalados, SLA). El número rojo del ícono y el título parpadeante avisan lo nuevo.
- **Su nombre arriba a la derecha:** abre su perfil y el cierre de sesión.
- **Luna/sol:** cambia entre tema claro y oscuro.

## 3. Crear un ticket (despachador y supervisor)
1. Pulse **Nuevo ticket**.
2. Elija **Tipo de solicitud** (Solicitud de Soporte Cliente o Soporte al Técnico), **Tipo de servicio** y **Solicitud específica** (puede escribir para filtrar).
3. Ingrese **Contrato** (clientes) u **OT** (técnicos), solo números. El sistema avisa si ya existe un ticket abierto con ese dato.
4. Para clientes complete nombre y nodo. Agregue comentarios y fotos (JPG/PNG, máx. 5 MB c/u, hasta 5 por tipo de evidencia): puede seleccionar, arrastrar o pegar con Ctrl+V en el formulario.
5. **Enviar a soporte.** El sistema lo enruta solo al equipo que atiende ese tipo.

## 4. Bandeja de tickets
- **Filtros por estado** según su rol (Trabajables, Míos, Validación, Escalados, Todos, etc.).
- **Ordenar:** recientes, antiguos o prioridad. **Buscar** por ID, asunto, persona, contrato u OT.
- Columnas: ticket, prioridad, estado, grupo, SLA restante y **Tiempo total** (creado → resuelto o al momento).
- Clic en una fila para ver el **detalle**: datos, solución, evidencia inicial y de solución (separadas, 5 y 5), historial completo y acciones según su rol.

## 5. Atender tickets (soporte)
- **Tomar ticket** (bandeja) o **Iniciar atención** (si ya está asignado a usted).
- **Registrar solución:** describa el diagnóstico y adjunte fotos de la solución si aplica → el ticket pasa a **Validación** y se avisa al despacho.
- **Escalar:** complete el dato faltante (Contrato/OT), elija el **área** (Tier3, Fixed Support, SSA, NOC, TTC Regional), motivo e instrucciones para despacho. El ticket queda en **Escalados** con su temporizador.
- **Recibida respuesta · continuar:** al responder el área, devuelve el ticket a su estado anterior para resolverlo.
- **Liberar a bandeja** devuelve el ticket al grupo. **Reasignar** lo mueve a un compañero del grupo.

## 6. Validar soluciones (despachador creador, supervisor de su grupo o admin)
- En **Validaciones** o en el detalle: **Aprobar solución** (cierra el ticket) o **Rechazar y devolver** (indique el motivo; vuelve a soporte).
- Si un ticket vuelve a validación, la notificación llega como nueva.

## 7. Escalados
- Vista exclusiva con área, motivo, instrucciones y tiempo que lleva escalado.
- El despacho lo ve en solo lectura y recibe notificación con las instrucciones de soporte.

## 8. Mi grupo
- Tabla del equipo: presencia real (**En línea** = conectado ahora), carga activa y, por persona, creados, pendientes, validación, cerrados y AHT. Filtros por estado (Todos/En línea/Ausentes) y rango (Hoy/Semana/Mes/Siempre).

## 9. Informes
- Filtros por grupo, servicio y rango (Hoy/Semana/Mes/Todo o fechas propias) + **Descargar CSV**.
- Tarjetas: entrantes, resueltos, AHT `[h]:mm:ss`, % SLA, proceso, vencidos, devueltos, escalados y tiempos por etapa (respuesta, atención, cierre, escalado).
- Gráficas de tráfico diario, AHT diario, dona por servicio y barras por grupo.

## 10. Administración (administrador y supervisor)
- **Usuarios:** crear (con clave o con invitación por correo), editar, activar/desactivar, restablecer contraseña. **Carga masiva** por CSV (plantilla descargable; columnas `email,first_name,last_name,role,teams`).
- **Grupos, equipos, tipos** (con equipo que atiende: Soporte A/B o automático) y **áreas de escalamiento**.
- **Auditoría** (solo administrador): quién creó/editó usuarios, cambios de rol, resets, bloqueos, catálogos y descargas; filtros por tiempo y acción.

## 11. Preguntas frecuentes
- **No me llega el correo:** revise spam; el enlace dura 1 hora; pida uno nuevo.
- **"Ya existe un ticket abierto":** abra ese ticket y documente allí, no duplique.
- **Foto con "Procesando texto…":** el sistema lee el texto en segundo plano; si no logra leerla, la analiza la IA y el resultado aparece solo.
- **Pegó una tabla de Excel y salió foto:** en campos de texto se pega como texto; fuera de ellos, como imagen.
- **Sesión vencida:** tras 1 día sin uso debe ingresar de nuevo; al cerrar la pestaña se cierra la sesión.
