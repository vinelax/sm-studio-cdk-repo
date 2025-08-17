# AWS CDK (Python) + GitHub Actions (OIDC)

This repo is wired so pushes to `main` can **deploy CDK** to AWS using **GitHub OIDC** (no long‑lived AWS keys).

## What’s inside
- `sm_cdk_app/` – main CDK stack (PublicInternet Sagemaker AI studio).
- `oidc_stack/` – one‑time stack to create the **GitHub OIDC IAM Role** in AWS.
- `.github/workflows/cdk-deploy.yml` – CI that runs `cdk diff` and `cdk deploy` on push.
- `app.py` – CDK app entrypoint.
- `cdk.json` – CDK config.
- `requirements.txt` – Python deps.

## One‑time setup
1) **Install prerequisites** (AWS CLI, Node.js LTS, Python 3.9+, CDK v2).  
2) **Authenticate** with AWS (access keys):  
   ```bash
   aws sts get-caller-identity
   ```
3) **Create a new GitHub repo**.
4) Bootstrap CDK in target account+region (once):  
   ```bash
   cdk bootstrap aws://<ACCOUNT_ID>/<REGION>
   ```

## Create the GitHub OIDC role (one‑time)
Edit `cdk.json` to set:
- `"GitHubRepoOwner": "<username>"`
- `"GitHubRepoName": "<repo-name>"`
- `"GitHubBranch": "main"` 

Then deploy the OIDC stack **locally** (it creates the role for GitHub Actions to assume):
```bash
pip install -r requirements.txt
npm i -g aws-cdk@2
cdk deploy OidcRoleStack
```

Copy the **Role ARN** output and paste it into `.github/workflows/cdk-deploy.yml` where indicated.

## CI/CD behavior
- On push to `main`, GitHub Actions:
  - Assumes the OIDC role in AWS
  - Installs dependencies
  - Runs `cdk synth`, `cdk diff`, `cdk deploy --require-approval never`

## Local development
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cdk synth
cdk diff
cdk deploy
```

## Teardown
Be careful—this deletes resources:
```bash
cdk destroy SmCdkAppStack
# To remove the OIDC role:
cdk destroy OidcRoleStack
```
