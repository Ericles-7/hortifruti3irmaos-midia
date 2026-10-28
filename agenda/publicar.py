"""Publica no Instagram o que está na hora em agenda/fila.json, pela API oficial (Graph API).

Roda no GitHub Actions (.github/workflows/publicar.yml). Precisa das variáveis de ambiente:
  IG_TOKEN    chave de acesso da Página do Facebook ligada ao Instagram (segredo do repositório)
  IG_USER_ID  id da conta do Instagram

Uso:
  python3 agenda/publicar.py           # publica o que venceu há no máximo 90 min
  python3 agenda/publicar.py testar    # só confere a chave e mostra o que publicaria agora
Depois de cada post, grava o status em fila.json e faz commit + push (para nunca repetir).
Para desligar o robô sem mexer em nada mais, apague o arquivo agenda/ATIVO.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

FILA = Path(__file__).with_name("fila.json")
ATIVO = Path(__file__).with_name("ATIVO")  # só publica com este arquivo presente (liga/desliga o robô)
API = "https://graph.facebook.com/v21.0"
ATRASO_MAXIMO = timedelta(minutes=90)  # depois disso o post perde a hora (ex.: "bom dia" à noite) e não sai


class ErroApi(Exception):
    pass


def chamar(metodo, caminho, **params):
    params["access_token"] = os.environ["IG_TOKEN"]
    dados = urllib.parse.urlencode(params).encode()
    if metodo == "GET":
        req = urllib.request.Request(f"{API}/{caminho}?{dados.decode()}")
    else:
        req = urllib.request.Request(f"{API}/{caminho}", data=dados, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        corpo = e.read().decode(errors="replace")
        try:
            corpo = json.loads(corpo)["error"]["message"]
        except (ValueError, KeyError):
            pass
        raise ErroApi(f"{e.code}: {corpo}") from None


def esperar_pronto(container, limite=600):
    """O Instagram processa a mídia antes de publicar (vídeo pode levar minutos)."""
    fim = time.time() + limite
    while True:
        status = chamar("GET", container, fields="status_code,status").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise ErroApi(f"processamento falhou ({status})")
        if time.time() > fim:
            raise ErroApi("processamento demorou demais")
        time.sleep(5)


def publicar(ig, p, fila):
    base, base_video = fila["base_url"], fila["base_video"]
    if p["tipo"] == "carrossel":
        filhos = [chamar("POST", f"{ig}/media", image_url=base + img, is_carousel_item="true")["id"]
                  for img in p["imagens"]]
        for f in filhos:
            esperar_pronto(f)
        container = chamar("POST", f"{ig}/media", media_type="CAROUSEL", children=",".join(filhos),
                           caption=p.get("legenda", ""))["id"]
    elif p["tipo"] == "reel":
        container = chamar("POST", f"{ig}/media", media_type="REELS", share_to_feed="true",
                           video_url=base_video.format(commit=p["commit"]) + p["video"],
                           cover_url=base + p["capa"], caption=p.get("legenda", ""))["id"]
    elif p["tipo"] == "story" and "video" in p:
        container = chamar("POST", f"{ig}/media", media_type="STORIES",
                           video_url=base_video.format(commit=p["commit"]) + p["video"])["id"]
    elif p["tipo"] == "story":
        container = chamar("POST", f"{ig}/media", media_type="STORIES", image_url=base + p["imagens"][0])["id"]
    else:
        raise ErroApi(f"tipo desconhecido: {p['tipo']}")
    esperar_pronto(container)
    return chamar("POST", f"{ig}/media_publish", creation_id=container)["id"]


def vencidos(fila, agora):
    fuso = ZoneInfo(fila["fuso"])
    for p in fila["postagens"]:
        quando = datetime.fromisoformat(f"{p['data']}T{p['hora']}").replace(tzinfo=fuso)
        if p["status"] == "pendente" and quando <= agora <= quando + ATRASO_MAXIMO:
            yield p


def salvar(fila, mensagem):
    FILA.write_text(json.dumps(fila, ensure_ascii=False, indent=2) + "\n")
    subprocess.run(["git", "add", str(FILA)], check=True)
    subprocess.run(["git", "commit", "-q", "-m", mensagem], check=True)
    for tentativa in range(4):
        subprocess.run(["git", "pull", "-q", "--rebase", "origin", "main"], check=False)
        if subprocess.run(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0:
            return
        time.sleep(2 ** (tentativa + 1))
    print("aviso: não consegui enviar o status para o GitHub", file=sys.stderr)


def main(modo="publicar"):
    if not os.environ.get("IG_TOKEN"):
        print("sem a chave IG_TOKEN nos segredos do repositório: nada a fazer")
        return
    ig = os.environ["IG_USER_ID"]
    fila = json.loads(FILA.read_text())
    agora = datetime.now(ZoneInfo(fila["fuso"]))

    if modo == "testar":
        conta = chamar("GET", ig, fields="username,name")
        print(f"chave OK: conta @{conta.get('username')} ({conta.get('name')})")
        print("publicaria agora:", [p["id"] for p in vencidos(fila, agora)] or "nada")
        return

    if not ATIVO.exists():
        print("publicação automática ainda não ligada (falta agenda/ATIVO): nada a fazer")
        return

    falhas = 0
    for p in list(vencidos(fila, agora)):
        try:
            media_id = publicar(ig, p, fila)
            p["status"], p["media_id"] = "publicado", media_id
            print(f"publicado {p['id']} -> {media_id}")
        except ErroApi as e:
            p["status"], p["erro"] = "erro", str(e)
            falhas += 1
            print(f"ERRO {p['id']}: {e}", file=sys.stderr)
        salvar(fila, f"Agenda: {p['status']} {p['id']}")
    if falhas:
        sys.exit(f"{falhas} post(s) com erro; veja agenda/fila.json")


if __name__ == "__main__":
    main(*sys.argv[1:2])
