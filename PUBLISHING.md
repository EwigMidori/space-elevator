# Publishing

Target GitHub repository:

```text
https://github.com/ewigmidori/space-elevator
```

## Local Preparation

```bash
git init
git branch -M main
git remote add origin git@github.com:ewigmidori/space-elevator.git
UV_CACHE_DIR=$PWD/.uv-cache uv lock
git add .
git commit -m "space-elevator: bootstrap portable pm harness"
```

## First Push

Run this from a network-enabled shell:

```bash
git push -u origin main
```

## Optional Release Build

```bash
uv build
```
