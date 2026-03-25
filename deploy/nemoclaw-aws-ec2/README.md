# NeMo Claw on AWS EC2 (Terraform)

Single Ubuntu 24.04 EC2 in the default VPC with Docker, Node.js 22, global `nemoclaw` CLI, and `nemoclaw-aux` systemd (`nemoclaw start` on boot).

## Prerequisites

- Terraform `>= 1.5`, AWS CLI v2 recommended
- An IAM **access key** whose ID looks like `AKIA...` (20 characters), not a username or password
- Default VPC with a route to the internet (public IPv4 on the instance)
- Optional EC2 key pair for SSH, or SSM only with `enable_ssm = true`

Spanish, step-by-step if you are stuck: [SETUP_MINIMO_ES.md](SETUP_MINIMO_ES.md).

## First-time AWS setup (do this once)

1. Sign in to the [IAM console](https://console.aws.amazon.com/iam/).
2. **Users** → **Create user** (for example `nemoclaw-terraform`) → attach permissions:
   - **Create policy** (JSON) and paste the contents of [`iam/terraform-deployer-policy.json`](iam/terraform-deployer-policy.json), **OR** attach `AdministratorAccess` if you accept broader rights while learning.
3. Open the user → **Security credentials** → **Create access key** (CLI). Copy **Access key** and **Secret** (shown once).
4. On your PC:

   ```powershell
   aws configure
   ```

   Paste the two values. Set **Default region** to the same region you will use in `terraform.tfvars` (`aws_region`).

5. Verify:

   ```powershell
   cd deploy/nemoclaw-aws-ec2
   .\scripts\preflight-aws.ps1
   ```

   You should see JSON from `sts get-caller-identity`.

### Common mistakes

- Putting a **login name** or **Cursor password** in `aws configure` — AWS only accepts keys from IAM.
- `InvalidClientTokenId` — wrong or expired keys, or stale `AWS_ACCESS_KEY_ID` in Windows environment variables overriding `~/.aws/credentials`.

## One-shot script (Windows)

From `deploy/nemoclaw-aws-ec2`:

```powershell
.\scripts\go.ps1          # preflight + init + plan (writes tfplan)
.\scripts\go.ps1 -Apply   # same, then apply without prompt
```

Optional: `.\scripts\go.ps1 -Profile my-sso-profile` or set `aws_profile` in `terraform.tfvars`.

## Manual flow

```bash
cd deploy/nemoclaw-aws-ec2
cp terraform.tfvars.example terraform.tfvars
# Edit: aws_region, allowed_ssh_cidr, key_name, optional secrets

terraform init
terraform plan
terraform apply
```

Use outputs: `public_ip`, `ssh_hint`, `ssm_session_hint`, `post_apply_steps`.

## Variables

See `variables.tf` and `terraform.tfvars.example`. Do not commit real values in `terraform.tfvars` (gitignored).

## Teardown

```bash
terraform destroy
```

## NemoClaw CLI (important)

The package named `nemoclaw` on **npmjs.org** is **not** the NVIDIA CLI (it is an unrelated stub). Install from GitHub:

```bash
npm install -g "github:NVIDIA/NemoClaw"
```

On Windows, you can run `scripts/setup-nemoclaw-telegram-windows.ps1` (Node 22+, Docker Desktop for `nemoclaw onboard`).
