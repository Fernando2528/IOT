# Especificación de Tópicos de Movimiento (`motion/state` y `motion/sequence`)

Prefijo configurado para el **Robot 12** (Grupo Materia 1 - Lunes, Grupo Proyecto 2):
- **Prefijo Base**: `UDFJC/carrrobot`
- **ID de Robot**: `12` (`robot12`, número **par** -> ejecuta `even.json`)
- **Prefijo Completo**: `UDFJC/carrrobot/robot12/`

---

## 1. Ejecución Inmediata de un Estado (`motion/state`)

- **Tópico completo**: `UDFJC/carrrobot/robot12/motion/state`
- **Payload JSON**:

```json
{
  "v_dm/s": 1.0,
  "w_deg/s": 5.7,
  "alpha0_deg": 0,
  "alpha1_deg": 45,
  "alpha2_deg": 30,
  "duration_s": 15.7
}
```

### Unidades y Valores por Defecto
- `v_dm/s`: Velocidad lineal del centro del robot en **decímetros por segundo** ($1\text{ dm/s} = 0.1\text{ m/s}$). Por defecto: `0`.
- `w_deg/s`: Velocidad angular en **grados por segundo** ($\text{rad/s} = \text{deg/s} \times \frac{\pi}{180}$). Por defecto: `0`.
- `alpha0_deg`: Ángulo de la base del brazo en grados (ignorable en chasis de 2 servos). Por defecto: `0`.
- `alpha1_deg`: Ángulo del primer eslabón (hombro) en grados. Por defecto: `0`.
- `alpha2_deg`: Ángulo del segundo eslabón (codo) en grados. Por defecto: `0`.
- `duration_s`: Duración de la maniobra y demora de transición del brazo en **segundos**. Por defecto: `1.0`.

---

## 2. Gestión de Secuencias y Coreografía (`motion/sequence`)

- **Tópico completo**: `UDFJC/carrrobot/robot12/motion/sequence`

### 2.1 Crear Secuencia (`"action": "create"`)
```json
{
  "action": "create",
  "name": "even",
  "run_at": "now",
  "states": [
    {
      "v_dm/s": 0,
      "w_deg/s": 45,
      "alpha0_deg": 0,
      "duration_s": 2
    }
  ]
}
```

### 2.2 Ejecutar o Programar Secuencia (`"action": "schedule"`)
- Ejecución inmediata:
```json
{
  "action": "schedule",
  "name": "even",
  "run_at": "now"
}
```
- Ejecución programada en fecha/hora ISO-8601:
```json
{
  "action": "schedule",
  "name": "even",
  "run_at": "2026-11-03T20:00:00Z"
}
```

### 2.3 Eliminar Secuencia (`"action": "delete"`)
```json
{
  "action": "delete",
  "name": "even"
}
```
