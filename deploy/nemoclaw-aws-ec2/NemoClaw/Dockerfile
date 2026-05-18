# NemoClaw sandbox image — OpenClaw + NemoClaw plugin inside OpenShell
#
# This file matches NVIDIA/NemoClaw main with autonomy-oriented additions:
# - Multi-agent workspaces (main, planner, coder, ops) under /sandbox/workspaces
# - /sandbox/apps for generated projects
# - Post-openclaw-doctor patch: restores gateway.controlUi pairing bypass + agent list
#   (doctor rewrites openclaw.json and drops those keys)
#
# Copy into your NemoClaw repo root (alongside nemoclaw/, scripts/) before
# openshell sandbox create --from Dockerfile --policy nemoclaw-blueprint/policies/openclaw-sandbox.yaml

ARG BASE_IMAGE=ghcr.io/nvidia/nemoclaw/sandbox-base:latest

FROM node:22-slim@sha256:4f77a690f2f8946ab16fe1e791a3ac0667ae1c3575c3e4d0d4589e9ed5bfaf3d AS builder
COPY nemoclaw/package.json nemoclaw/tsconfig.json /opt/nemoclaw/
COPY nemoclaw/src/ /opt/nemoclaw/src/
WORKDIR /opt/nemoclaw
RUN npm install && npm run build

FROM ${BASE_IMAGE}

RUN (apt-get remove --purge -y gcc gcc-12 g++ g++-12 cpp cpp-12 make \
        netcat-openbsd netcat-traditional ncat 2>/dev/null || true) \
    && apt-get autoremove --purge -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/nemoclaw/dist/ /opt/nemoclaw/dist/
COPY nemoclaw/openclaw.plugin.json /opt/nemoclaw/
COPY nemoclaw/package.json nemoclaw/package-lock.json /opt/nemoclaw/
COPY nemoclaw-blueprint/ /opt/nemoclaw-blueprint/

WORKDIR /opt/nemoclaw
RUN npm ci --omit=dev

RUN mkdir -p /sandbox/.nemoclaw/blueprints/0.1.0 \
    && cp -r /opt/nemoclaw-blueprint/* /sandbox/.nemoclaw/blueprints/0.1.0/

COPY scripts/nemoclaw-start.sh /usr/local/bin/nemoclaw-start
RUN chmod +x /usr/local/bin/nemoclaw-start

ARG NEMOCLAW_MODEL=nvidia/nemotron-3-super-120b-a12b
ARG NEMOCLAW_PROVIDER_KEY=nvidia
ARG NEMOCLAW_PRIMARY_MODEL_REF=nvidia/nemotron-3-super-120b-a12b
ARG CHAT_UI_URL=http://127.0.0.1:18789
ARG NEMOCLAW_INFERENCE_BASE_URL=https://inference.local/v1
ARG NEMOCLAW_INFERENCE_API=openai-completions
ARG NEMOCLAW_INFERENCE_COMPAT_B64=e30=
ARG NEMOCLAW_BUILD_ID=default

ENV NEMOCLAW_MODEL=${NEMOCLAW_MODEL} \
    NEMOCLAW_PROVIDER_KEY=${NEMOCLAW_PROVIDER_KEY} \
    NEMOCLAW_PRIMARY_MODEL_REF=${NEMOCLAW_PRIMARY_MODEL_REF} \
    CHAT_UI_URL=${CHAT_UI_URL} \
    NEMOCLAW_INFERENCE_BASE_URL=${NEMOCLAW_INFERENCE_BASE_URL} \
    NEMOCLAW_INFERENCE_API=${NEMOCLAW_INFERENCE_API} \
    NEMOCLAW_INFERENCE_COMPAT_B64=${NEMOCLAW_INFERENCE_COMPAT_B64}

WORKDIR /sandbox
USER sandbox

RUN mkdir -p /sandbox/workspaces/main /sandbox/workspaces/planner \
        /sandbox/workspaces/coder /sandbox/workspaces/ops /sandbox/apps

RUN python3 -c "\
import base64, json, os, secrets; \
from urllib.parse import urlparse; \
model = os.environ['NEMOCLAW_MODEL']; \
chat_ui_url = os.environ['CHAT_UI_URL']; \
provider_key = os.environ['NEMOCLAW_PROVIDER_KEY']; \
primary_model_ref = os.environ['NEMOCLAW_PRIMARY_MODEL_REF']; \
inference_base_url = os.environ['NEMOCLAW_INFERENCE_BASE_URL']; \
inference_api = os.environ['NEMOCLAW_INFERENCE_API']; \
inference_compat = json.loads(base64.b64decode(os.environ['NEMOCLAW_INFERENCE_COMPAT_B64']).decode('utf-8')); \
parsed = urlparse(chat_ui_url); \
chat_origin = f'{parsed.scheme}://{parsed.netloc}' if parsed.scheme and parsed.netloc else 'http://127.0.0.1:18789'; \
origins = ['http://127.0.0.1:18789']; \
origins = list(dict.fromkeys(origins + [chat_origin])); \
providers = { \
    provider_key: { \
        'baseUrl': inference_base_url, \
        'apiKey': 'unused', \
        'api': inference_api, \
        'models': [{**({'compat': inference_compat} if inference_compat else {}), 'id': model, 'name': primary_model_ref, 'reasoning': False, 'input': ['text'], 'cost': {'input': 0, 'output': 0, 'cacheRead': 0, 'cacheWrite': 0}, 'contextWindow': 131072, 'maxTokens': 4096}] \
    } \
}; \
agent_list = [ \
    {'id': 'main', 'workspace': '/sandbox/workspaces/main'}, \
    {'id': 'planner', 'workspace': '/sandbox/workspaces/planner'}, \
    {'id': 'coder', 'workspace': '/sandbox/workspaces/coder'}, \
    {'id': 'ops', 'workspace': '/sandbox/workspaces/ops'}, \
]; \
config = { \
    'agents': {'defaults': {'model': {'primary': primary_model_ref}}, 'list': agent_list}, \
    'models': {'mode': 'merge', 'providers': providers}, \
    'channels': {'defaults': {'configWrites': False}}, \
    'gateway': { \
        'mode': 'local', \
        'controlUi': { \
            'allowInsecureAuth': True, \
            'dangerouslyDisableDeviceAuth': True, \
            'allowedOrigins': origins, \
        }, \
        'trustedProxies': ['127.0.0.1', '::1'], \
        'auth': {'token': secrets.token_hex(32)} \
    } \
}; \
path = os.path.expanduser('~/.openclaw/openclaw.json'); \
json.dump(config, open(path, 'w'), indent=2); \
os.chmod(path, 0o600)"

RUN openclaw doctor --fix > /dev/null 2>&1 || true \
    && openclaw plugins install /opt/nemoclaw > /dev/null 2>&1 || true

RUN python3 -c "\
import json, os; \
p = os.path.expanduser('~/.openclaw/openclaw.json'); \
primary = os.environ['NEMOCLAW_PRIMARY_MODEL_REF']; \
c = json.load(open(p)); \
g = c.setdefault('gateway', {}); \
cu = g.setdefault('controlUi', {}); \
cu['allowInsecureAuth'] = True; \
cu['dangerouslyDisableDeviceAuth'] = True; \
a = c.setdefault('agents', {}); \
a.setdefault('defaults', {})['model'] = {'primary': primary}; \
by = {x['id']: x for x in (a.get('list') or []) if isinstance(x, dict) and 'id' in x}; \
by.update({'main': {'id': 'main', 'workspace': '/sandbox/workspaces/main'}, 'planner': {'id': 'planner', 'workspace': '/sandbox/workspaces/planner'}, 'coder': {'id': 'coder', 'workspace': '/sandbox/workspaces/coder'}, 'ops': {'id': 'ops', 'workspace': '/sandbox/workspaces/ops'}}); \
a['list'] = [by[k] for k in ('main', 'planner', 'coder', 'ops')]; \
json.dump(c, open(p, 'w'), indent=2); \
os.chmod(p, 0o600)"

USER root
RUN chown root:root /sandbox/.openclaw \
    && find /sandbox/.openclaw -mindepth 1 -maxdepth 1 -exec chown -h root:root {} + \
    && chmod 755 /sandbox/.openclaw \
    && chmod 444 /sandbox/.openclaw/openclaw.json

RUN sha256sum /sandbox/.openclaw/openclaw.json > /sandbox/.openclaw/.config-hash \
    && chmod 444 /sandbox/.openclaw/.config-hash \
    && chown root:root /sandbox/.openclaw/.config-hash

ENTRYPOINT ["/usr/local/bin/nemoclaw-start"]
CMD ["/bin/bash"]
