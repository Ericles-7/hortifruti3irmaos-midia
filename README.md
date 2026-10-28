# Hortifruti 3 Irmãos — mídia do Instagram

Imagens e vídeos prontos para publicar no @hortifruti3irmaos_uirauna.

Este repositório é **público de propósito**: o Instagram baixa cada post de um endereço público. Por isso aqui ficam **só** os arquivos finais, os mesmos que vão para o perfil. Programas, agenda e roteiros ficam no repositório privado `hortifruti3irmaos-instagram`.

- Carrosséis do feed: 1080×1350, na raiz (`<código>-<tema>-<n>.jpg`).
- Stories: 1080×1920, em `stories/banco/`.
- Reels: vídeo e capa, em `reels/`.

## Publicação automática

O GitHub Actions (`.github/workflows/publicar.yml`) roda nos horários da programação e publica no Instagram o que está em `agenda/fila.json`, pela API oficial (`agenda/publicar.py`). A chave de acesso fica no segredo `IG_TOKEN` do repositório. O robô só publica se existir o arquivo `agenda/ATIVO`; para desligar, é só apagar esse arquivo.
