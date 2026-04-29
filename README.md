# Bootstrap CVE-2024-6485 XSS Probes

Repositório com scripts de validação controlada para a **CVE-2024-6485**, uma vulnerabilidade de **Cross-Site Scripting (XSS)** associada ao **Bootstrap Button Plugin** e ao uso inseguro do atributo `data-loading-text`.

A falha pode ocorrer quando conteúdo não confiável é inserido no atributo `data-loading-text` e o estado de loading do botão é acionado. Dependendo da implementação da página, esse conteúdo pode ser interpretado como HTML e executar JavaScript no navegador do usuário.

O objetivo dos scripts deste repositório é apoiar validações técnicas em ambientes autorizados, com foco em comprovação controlada da vulnerabilidade.

### Versões afetadas

De acordo com advisories públicos, a vulnerabilidade afeta versões do pacote Bootstrap no intervalo:

```text
>= 1.4.0 <= 3.4.1
```

A validação não deve considerar apenas a versão do Bootstrap. Também é necessário confirmar se a aplicação realmente utiliza o **Button Plugin** e se existe uso do atributo `data-loading-text` em elementos interativos.

Em termos práticos: só ter Bootstrap antigo não fecha o diagnóstico. É necessário existir o componente vulnerável e um fluxo que permita a execução do payload.

---

## Resumo da vulnerabilidade

A **CVE-2024-6485** permite a execução de JavaScript no navegador quando um valor inseguro é inserido no atributo `data-loading-text` do Bootstrap Button Plugin e o botão entra no estado de loading.

Esse comportamento pode ser explorado em cenários onde a aplicação reflete ou insere conteúdo controlável pelo usuário nesse atributo sem sanitização adequada.

Impactos possíveis:

- execução de JavaScript no navegador da vítima;
- roubo de sessão, dependendo das proteções aplicadas;
- manipulação da página;
- redirecionamento malicioso;
- captura de dados inseridos pelo usuário;
- apoio a ataques de phishing dentro da própria aplicação.

---

## Diferença entre os scripts

| Script | Objetivo | Quando usar |
|---|---|---|
| `bootstrap_cve_2024_6485_param_check.py` | Valida se parâmetros de URL são refletidos em `data-loading-text` e tenta acionar o comportamento vulnerável. | Usar quando houver suspeita de reflexo de entrada do usuário em botões ou atributos HTML. |
| `bootstrap_cve_2024_6485_dom_probe.py` | Valida o comportamento do DOM, presença de jQuery, Button Plugin e elementos candidatos. | Usar como prova técnica principal para confirmar o sink vulnerável no DOM. |

Em resumo, o `bootstrap_cve_2024_6485_param_check.py` é mais indicado para validar entrada via parâmetro refletido na página, enquanto o `bootstrap_cve_2024_6485_dom_probe.py` é mais indicado para confirmar o comportamento vulnerável diretamente no DOM e no componente Bootstrap.

---

## Fluxo recomendado de validação

A ordem recomendada de uso é:

```text
1. Identificar se a aplicação usa Bootstrap legado
   ↓
2. Verificar se há jQuery e Bootstrap Button Plugin
   ↓
3. Executar bootstrap_cve_2024_6485_dom_probe.py
   ↓
4. Executar bootstrap_cve_2024_6485_param_check.py em páginas com parâmetros
   ↓
5. Registrar evidência e saída do teste
```

---
## Cenário ideal para teste

Os scripts devem ser usados em páginas que tenham maior chance de utilizar o Bootstrap Button Plugin, como:

```text
/login
/formulario
/cadastro
/checkout
/painel
/admin
/contato
/recuperar-senha
```

O alvo ideal é uma página que tenha:

- Bootstrap em versão vulnerável;
- jQuery carregado;
- botões ou links com classe `.btn`;
- uso de `data-loading-text`;
- ações de loading em botões;
- parâmetros refletidos na página ou no DOM.

Evite testar apenas a home se ela não possuir botões, formulários ou componentes interativos. Testar home estática e concluir que não é vulnerável é o clássico falso conforto corporativo.

---

# Requisitos

## Dependências

Dependências principais:

```text
Python 3
Selenium
Google Chrome ou Chromium
ChromeDriver compatível
webdriver-manager
```

Instalação das dependências Python:

```bash
python3 -m pip install selenium webdriver-manager
```

Instalação do Chromium em Kali/Debian/Ubuntu:

```bash
sudo apt update
sudo apt install chromium -y
```

Validação rápida:

```bash
python3 -c "import selenium; print('Selenium instalado com sucesso')"
```

---

# Uso dos scripts

## 1. bootstrap_cve_2024_6485_param_check.py

### Descrição

O `bootstrap_cve_2024_6485_param_check.py` é utilizado para validar se parâmetros enviados pela URL são refletidos no atributo `data-loading-text` de elementos da página e se esse comportamento pode acionar a vulnerabilidade associada à **CVE-2024-6485**.

O script testa parâmetros comuns, injeta um payload controlado e verifica se ele aparece dentro de `data-loading-text`. Caso encontre reflexo, tenta acionar o estado de loading do botão para validar se existe possibilidade de execução do conteúdo.

### Quando usar

Use este script quando houver suspeita de que valores enviados pela URL sejam utilizados dinamicamente pela aplicação em botões, mensagens, labels, títulos ou atributos HTML.

Ele é mais indicado para cenários onde existe reflexo de entrada do usuário na página, como mensagens de erro, status de operação, textos de botão ou parâmetros usados para montar conteúdo visual.

### Exemplo básico

```bash
python3 bootstrap_cve_2024_6485_param_check.py -u "https://exemplo.com.br/login"
```

### Exemplo com navegador visível

```bash
python3 bootstrap_cve_2024_6485_param_check.py -u "https://exemplo.com.br/login" --headful
```

### Exemplo informando o caminho do Chrome/Chromium

```bash
python3 bootstrap_cve_2024_6485_param_check.py -u "https://exemplo.com.br/login" --binary "/usr/bin/chromium"
```

---

## 2. bootstrap_cve_2024_6485_dom_probe.py

### Descrição

O `bootstrap_cve_2024_6485_dom_probe.py` é utilizado para validar o comportamento do DOM relacionado à **CVE-2024-6485**. Ele verifica a presença de elementos candidatos, jQuery, Bootstrap Button Plugin e tenta acionar o payload no contexto real do navegador.

O script injeta um payload controlado no atributo `data-loading-text`, aciona o estado de loading do botão e verifica se houve execução de JavaScript.

### Quando usar

Use este script como validação principal quando o objetivo for confirmar se a página possui o componente vulnerável e se o Bootstrap Button Plugin processa o atributo `data-loading-text` de forma insegura.

Ele é mais indicado para páginas que possuem botões Bootstrap, formulários, fluxos de login, cadastro, checkout, recuperação de senha ou qualquer tela com interação baseada em botões.

### Exemplo básico

```bash
python3 bootstrap_cve_2024_6485_dom_probe.py -u "https://exemplo.com.br/login"
```

### Exemplo em modo headless

```bash
python3 bootstrap_cve_2024_6485_dom_probe.py -u "https://exemplo.com.br/login" --headless
```

### Exemplo informando o caminho do Chrome/Chromium

```bash
python3 bootstrap_cve_2024_6485_dom_probe.py -u "https://exemplo.com.br/login" --binary "/usr/bin/chromium"
```

---

# Como escolher qual script usar

| Situação | Script recomendado |
|---|---|
| Quero validar se um parâmetro da URL reflete em `data-loading-text` | `bootstrap_cve_2024_6485_param_check.py` |
| Quero validar se o componente Bootstrap executa o payload no DOM | `bootstrap_cve_2024_6485_dom_probe.py` |
| Tenho uma página com botões Bootstrap e quero evidência técnica | `bootstrap_cve_2024_6485_dom_probe.py` |
| Tenho parâmetros como `message`, `status`, `label`, `title` refletindo na página | `bootstrap_cve_2024_6485_param_check.py` |
| Não sei por onde começar | Execute primeiro o `dom_probe`, depois o `param_check` |

---

# Boas práticas de validação

Antes de reportar a vulnerabilidade, confirme:

- se a página carrega Bootstrap em versão afetada;
- se existe jQuery;
- se o Button Plugin está disponível;
- se há elementos com `data-loading-text`;
- se o payload é refletido no DOM;
- se o estado de loading do botão é acionado;
- se houve execução real do JavaScript;
- se o comportamento ocorre em fluxo acessível ao usuário.

---

# Limitações

A simples presença de Bootstrap vulnerável não significa, sozinha, que existe exploração prática.

Para que a vulnerabilidade seja explorável, normalmente é necessário que:

- a aplicação utilize o Button Plugin;
- o atributo `data-loading-text` esteja presente ou seja manipulado;
- conteúdo não confiável seja inserido nesse atributo;
- o botão tenha o estado de loading acionado;
- não existam controles eficazes de sanitização, encoding ou CSP.

O teste deve ser feito nas páginas certas. Um resultado negativo em uma única tela não elimina a possibilidade de exposição em outras partes da aplicação.

---

# Mitigação

Atualize o Bootstrap para uma versão suportada e remova dependências legadas quando possível. Caso a atualização imediata não seja viável, revise o uso de `data-loading-text`, impeça que dados controlados pelo usuário sejam inseridos nesse atributo, aplique sanitização adequada, utilize encoding de saída e implemente uma política de Content Security Policy para reduzir o risco de execução de JavaScript inline.

Além disso, recomenda-se revisar páginas antigas, componentes reutilizáveis, templates de front-end e fluxos de formulário que utilizem Bootstrap legado, pois o risco tende a aparecer em telas menos monitoradas e componentes herdados.

---

# Referências

```text
https://nvd.nist.gov/vuln/detail/CVE-2024-6485
https://www.cve.org/CVERecord?id=CVE-2024-6485
https://security.snyk.io/vuln/SNYK-JS-BOOTSTRAP-7444617

```
---

# Aviso legal

Estes scripts devem ser utilizados apenas em ambientes autorizados.

A finalidade deste repositório é apoiar atividades legítimas de segurança, como pentest autorizado, validação controlada de vulnerabilidades, laboratório, estudo técnico e comprovação segura de risco.

O uso contra sistemas sem autorização é proibido.
