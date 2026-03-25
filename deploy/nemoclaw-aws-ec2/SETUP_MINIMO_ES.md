# Si no puedes con la consola de AWS (guía mínima)

## Opción 1 — Que lo haga otra persona (lo más fácil)

Envía este texto a quien **sí** tenga acceso de administrador a la cuenta AWS:

> Crea un usuario IAM (por ejemplo `nemoclaw-deploy`) con la política en JSON del archivo `iam/terraform-deployer-policy.json` de este repo (o temporalmente `AdministratorAccess`). Genera **Access key** para CLI y pásame el **Access key ID** (empieza por AKIA) y el **Secret** (solo una vez). La región será la que usemos en el despliegue (por ejemplo `us-east-2`).

Tú solo tendrías que ejecutar en PowerShell:

```powershell
aws configure
```

y pegar lo que te pasen (dos líneas largas, no contraseñas de Cursor ni de correo).

---

## Opción 2 — Cuenta AWS solo tuya (sin “experto”)

1. Crea cuenta en [aws.amazon.com](https://aws.amazon.com) (tarjeta; muchas regiones tienen capa gratuita limitada).
2. Entra a la consola → arriba a la derecha tu nombre → **Security credentials**.
3. Baja hasta **Access keys** → **Create access key** → tipo **CLI** → crea y **copia las dos claves** (la secreta solo se muestra una vez).
4. En tu PC:

   ```powershell
   aws configure
   ```

   Pega **Access Key ID** y **Secret**. Región: la misma que pondrás en `terraform.tfvars` (`aws_region`).

5. En la carpeta del proyecto:

   ```powershell
   cd G:\NeMo-Agent-Toolkit\deploy\nemoclaw-aws-ec2
   .\scripts\go.ps1
   ```

**Nota:** Usar claves del usuario **root** sirve para probar, pero en producción es mejor un usuario IAM; para “solo probar una vez” mucha gente empieza así.

---

## Opción 3 — No puedes / no quieres AWS

Este Terraform **solo sirve para EC2 en AWS**. Si no tienes cuenta o permisos:

- Puedes usar **NeMo Claw en tu PC** (Windows): instalar Node, luego `npm install -g nemoclaw` y seguir la documentación del paquete (sin servidor en la nube).
- Otro proveedor (Azure, GCP) **no** está cubierto por esta carpeta; habría que adaptar o usar otra guía.

---

## Si te atascas en un paso concreto

Di exactamente qué ves: por ejemplo “no encuentro Security credentials”, “no me deja crear access key”, o pega **solo el mensaje de error** (sin pegar claves ni secretos).
