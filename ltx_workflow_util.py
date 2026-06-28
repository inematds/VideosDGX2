#!/usr/bin/env python3
"""
ltx_workflow_util.py
====================
Utilitario para converter workflows ComfyUI do formato UI (chaves "nodes"+"links",
exportado pela interface grafica) para o formato API (dict id -> {class_type, inputs})
exigido pelo endpoint POST /prompt.

Tambem oferece:
  - poda de nos "muted"/"bypassed" (mode 2/4) e de subgrafos inalcancaveis;
  - resolucao de valores de COMBO/ENUM contra o object_info real do servidor
    (ex.: nome de checkpoint do workflow != nome instalado);
  - helpers de submissao e polling no /prompt e /history.

Schema do object_info: cada input e
    [TYPE]                      -> tipo simples (ex.: "INT", "MODEL")
    [TYPE, {opts}]              -> tipo com opcoes
    [[a,b,c], {opts}]           -> COMBO "legado" (lista inline de escolhas)
    ["COMBO", {"options":[...]}]-> COMBO v3 (escolhas em opts["options"])
"""

import json
import time
import uuid
import urllib.request
import urllib.error


# --------------------------------------------------------------------------- #
# object_info
# --------------------------------------------------------------------------- #
def fetch_object_info(base_url, timeout=120):
    """Baixa o object_info completo do ComfyUI."""
    with urllib.request.urlopen(base_url.rstrip("/") + "/object_info", timeout=timeout) as r:
        return json.load(r)


def _input_spec_iter(class_info):
    """
    Itera (nome, spec, secao) sobre required + optional, na ORDEM declarada.
    Essa ordem e a usada para casar widgets_values com nomes de input.
    """
    inp = (class_info or {}).get("input", {}) or {}
    for sect in ("required", "optional"):
        for name, spec in (inp.get(sect, {}) or {}).items():
            yield name, spec, sect


def _spec_type(spec):
    """Retorna o tipo declarado de um input spec."""
    if not isinstance(spec, list) or not spec:
        return None
    return spec[0]


def _spec_combo_options(spec):
    """
    Se o spec representa um COMBO simples, retorna a lista de opcoes; senao None.
    Cobre o formato legado [[..], {..}] e o v3 ["COMBO", {"options":[..]}].
    NAO cobre COMFY_DYNAMICCOMBO_V3 (cujas options sao dicts) -> ver _dynamic_combo_options.
    """
    if not isinstance(spec, list) or not spec:
        return None
    head = spec[0]
    if isinstance(head, list):
        return head  # legado: escolhas inline
    if isinstance(head, str) and head.upper() == "COMBO":
        opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        out = list(opts.get("options", []))
        # se as "options" sao dicts -> e dynamic combo, nao combo simples
        if out and isinstance(out[0], dict):
            return None
        return out
    return None


def _dynamic_combo_options(spec):
    """
    Para COMFY_DYNAMICCOMBO_V3: retorna lista de dicts {key, inputs:{required:{...}}}.
    Cada opcao tem uma 'key' (o valor selecionavel) e sub-inputs que ficam ativos
    quando aquela key e escolhida. Senao for dynamic combo, retorna None.
    """
    if not isinstance(spec, list) or not spec:
        return None
    head = spec[0]
    if isinstance(head, str) and head.upper() == "COMFY_DYNAMICCOMBO_V3":
        opts = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
        return list(opts.get("options", []))
    return None


def _is_dynamic_combo(spec):
    return _dynamic_combo_options(spec) is not None


def _is_link_input(spec):
    """
    Heuristica: inputs cujo tipo e um nome de classe maiusculo (MODEL, LATENT,
    CONDITIONING, IMAGE, VAE, CLIP, ...) sao tipicamente conexoes, nao widgets.
    Tipos primitivos (INT, FLOAT, STRING, BOOLEAN) e COMBO sao widgets.
    Mesmo assim a conversao real usa as conexoes do grafo; isto so serve para
    distribuir os widgets_values pelos nomes de input corretos.
    """
    WIDGET_TYPES = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO",
                    "COMFY_DYNAMICCOMBO_V3"}
    t = _spec_type(spec)
    if isinstance(t, list):
        return False  # combo legado = widget
    if not isinstance(t, str):
        return False
    tu = t.upper()
    if tu == "COMFY_MATCHTYPE_V3":
        return True  # match type = sempre conexao (IMAGE/MASK/etc.)
    return tu not in WIDGET_TYPES


# --------------------------------------------------------------------------- #
# COMBO resolution
# --------------------------------------------------------------------------- #
def resolve_combo_value(value, options, prefer_substrings=None):
    """
    Garante que 'value' seja um valor valido em 'options'. Estrategia:
      1. match exato;
      2. match por basename (workflow usa 'a/b/c.safetensors', instalado e 'c.safetensors');
      3. match por substring entre value e cada opcao (qualquer direcao);
      4. prefer_substrings: primeira opcao que contenha um desses termos;
      5. primeira opcao.
    """
    if not options:
        return value
    if value in options:
        return value

    sval = str(value) if value is not None else ""
    base = sval.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

    # 2) basename igual
    for o in options:
        ob = str(o).rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
        if ob == base and base:
            return o

    # 3) substring mutua
    if sval:
        for o in options:
            so = str(o)
            if base and (base in so or so.rsplit("/", 1)[-1] == base):
                return o
        for o in options:
            so = str(o)
            if so in sval or sval in so:
                return o

    # 4) preferencias
    for sub in (prefer_substrings or []):
        for o in options:
            if sub.lower() in str(o).lower():
                return o

    # 5) fallback
    return options[0]


# --------------------------------------------------------------------------- #
# UI -> API
# --------------------------------------------------------------------------- #
def _build_link_index(ui_wf):
    """
    Mapeia link_id -> (src_node_id, src_slot).
    Formato de link na UI: [link_id, src_node, src_slot, dst_node, dst_slot, type].
    """
    idx = {}
    for L in ui_wf.get("links", []) or []:
        if not L:
            continue
        lid, s, ss = L[0], L[1], L[2]
        idx[lid] = (s, ss)
    return idx


def _muted(node):
    """mode 2 (muted) ou 4 (bypassed/never) => no nao executa."""
    return node.get("mode", 0) in (2, 4)


def ui_to_api(ui_wf, object_info, drop_node_ids=None,
              combo_prefer=None):
    """
    Converte um workflow UI -> dict API {str(id): {class_type, inputs}}.

    - Ignora nos muted/bypassed (mode 2/4) e os de drop_node_ids.
    - Resolve cada input:
        * se ha conexao (node.inputs[i].link), vira [src_id, src_slot];
          a conexao e mantida APENAS se a origem ainda existe no grafo final.
        * senao, e widget -> casa widgets_values na ordem dos inputs widget do schema.
    - Valores de COMBO sao resolvidos contra object_info (resolve_combo_value).

    combo_prefer: dict {(class_type, input_name): [substrings...]} para guiar
    a escolha de COMBO quando o valor do workflow nao existir no servidor.
    """
    drop = set(drop_node_ids or [])
    combo_prefer = combo_prefer or {}
    link_idx = _build_link_index(ui_wf)

    nodes = ui_wf.get("nodes", [])
    by_id = {n["id"]: n for n in nodes}

    # conjunto de nos que VAO existir no API
    keep_ids = set()
    for n in nodes:
        nid = n["id"]
        if nid in drop:
            continue
        if _muted(n):
            continue
        ctype = n.get("type")
        if ctype not in object_info:
            # no sem schema no servidor: nao da pra submeter -> descarta
            continue
        keep_ids.add(nid)

    api = {}

    for n in nodes:
        nid = n["id"]
        if nid not in keep_ids:
            continue
        ctype = n["type"]
        class_info = object_info[ctype]

        # ordem dos inputs do schema
        specs = list(_input_spec_iter(class_info))
        spec_by_name = {name: spec for name, spec, _ in specs}

        # quais inputs do schema sao widgets (na ordem) -> casar widgets_values
        widget_names_in_order = [name for name, spec, _ in specs
                                 if not _is_link_input(spec)]

        # nomes vindos de conexao (inputs declarados no no, com link valido)
        connected = {}  # name -> [src_id, src_slot]
        node_inputs = n.get("inputs", []) or []
        for inp in node_inputs:
            link = inp.get("link")
            name = inp.get("name")
            if link is None or name is None:
                continue
            src = link_idx.get(link)
            if not src:
                continue
            src_id, src_slot = src
            # so mantem se a origem sobreviveu a poda
            if src_id in keep_ids:
                # ComfyUI exige id de no como STRING na referencia de link
                connected[name] = [str(src_id), int(src_slot)]

        # widgets_values: a UI mantem, na lista posicional, UMA entrada por
        # widget na ordem do schema -- inclusive para widgets que foram
        # convertidos em socket (conexao). Por isso o cursor posicional avanca
        # para TODO widget do schema; so escrevemos o valor quando o input NAO
        # esta conectado. (Isto corrige o desalinhamento que jogava o valor de
        # 'length' em 'batch_size', por exemplo.)
        wv = n.get("widgets_values", [])
        if isinstance(wv, dict):
            wv_by_name = dict(wv)
            wv_list = None
        else:
            wv_by_name = None
            wv_list = list(wv) if wv is not None else []

        inputs = {}

        # 1) conexoes primeiro
        for name, ref in connected.items():
            inputs[name] = ref

        # 2) widgets posicionais (com tratamento de COMFY_DYNAMICCOMBO_V3)
        wi = 0

        def _next_pos():
            nonlocal wi
            v = wv_list[wi] if (wv_list is not None and wi < len(wv_list)) else None
            wi += 1
            return v

        for name in widget_names_in_order:
            spec = spec_by_name.get(name)
            connected_here = name in inputs

            # --- dynamic combo: consome a key + sub-inputs ativos ---
            dyn = _dynamic_combo_options(spec)
            if dyn is not None:
                if wv_by_name is not None:
                    key = wv_by_name.get(name)
                else:
                    key = _next_pos()
                # localizar a opcao escolhida (por key)
                chosen = None
                keys = [o.get("key") for o in dyn]
                if key not in keys and keys:
                    key = keys[0]  # fallback: primeira opcao valida
                for o in dyn:
                    if o.get("key") == key:
                        chosen = o
                        break
                if not connected_here and key is not None:
                    inputs[name] = key
                # sub-inputs da opcao escolhida (consomem valores na ordem).
                # ComfyUI espera a chave PONTILHADA "<combo>.<sub>" no dict de
                # inputs (ex.: "resize_type.longer_size").
                sub_req = ((chosen or {}).get("inputs", {}) or {}).get("required", {}) or {}
                for sub_name, sub_spec in sub_req.items():
                    dotted = f"{name}.{sub_name}"
                    if wv_by_name is not None:
                        sval = wv_by_name.get(dotted, wv_by_name.get(sub_name))
                    else:
                        sval = _next_pos()
                    sopts = _spec_combo_options(sub_spec)
                    if sopts is not None:
                        sval = resolve_combo_value(
                            sval, sopts, combo_prefer.get((ctype, sub_name)))
                    if dotted not in inputs and sval is not None:
                        inputs[dotted] = sval
                continue

            # --- widget normal ---
            if wv_by_name is not None:
                val = wv_by_name.get(name)
            else:
                val = _next_pos()  # avanca cursor mesmo se conectado
            if connected_here:
                continue  # ja resolvido por conexao; valor descartado
            opts = _spec_combo_options(spec)
            if opts is not None:
                prefer = combo_prefer.get((ctype, name))
                val = resolve_combo_value(val, opts, prefer)
            if val is not None:
                inputs[name] = val

        api[str(nid)] = {"class_type": ctype, "inputs": inputs}

    return api


def prune_unreachable(api_wf, output_ids):
    """
    Mantem apenas os nos alcancaveis (por dependencia reversa) a partir dos
    output_ids dados (lista de ids como string). Retorna novo dict API.
    Util para remover ramos paralelos (ex.: segundo SaveVideo) que nao queremos.
    """
    output_ids = [str(i) for i in output_ids]
    keep = set()
    stack = list(output_ids)
    while stack:
        nid = stack.pop()
        if nid in keep or nid not in api_wf:
            continue
        keep.add(nid)
        for v in api_wf[nid]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], (int, str)):
                stack.append(str(v[0]))
    return {k: v for k, v in api_wf.items() if k in keep}


# --------------------------------------------------------------------------- #
# Submissao / polling
# --------------------------------------------------------------------------- #
def submit_prompt(base_url, api_wf, client_id=None, timeout=60):
    """POST /prompt. Retorna (prompt_id, raw_response_dict). Levanta em erro HTTP."""
    client_id = client_id or str(uuid.uuid4())
    payload = json.dumps({"prompt": api_wf, "client_id": client_id}).encode("utf-8")
    req = urllib.request.Request(
        base_url.rstrip("/") + "/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
            return data.get("prompt_id"), data
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body}
        # erro de validacao do ComfyUI vem com 400 e corpo JSON detalhado
        return None, {"http_status": e.code, "error": data}


def get_history(base_url, prompt_id, timeout=30):
    """GET /history/<id>. Retorna o dict da entrada (ou {} se ainda nao houver)."""
    url = base_url.rstrip("/") + "/history/" + str(prompt_id)
    with urllib.request.urlopen(url, timeout=timeout) as r:
        data = json.load(r)
    return data.get(str(prompt_id), {})


def wait_for_completion(base_url, prompt_id, poll_every=3, max_wait=1800,
                        on_tick=None):
    """
    Faz polling em /history ate o prompt terminar (status completed) ou ate
    aparecer erro. Retorna dict:
        {"status": "completed"|"error"|"timeout", "outputs": {...}, "messages": [...],
         "files": [list de nomes mp4/png salvos], "raw": <entry>}
    """
    start = time.time()
    while True:
        entry = {}
        try:
            entry = get_history(base_url, prompt_id)
        except Exception:
            entry = {}

        status = (entry.get("status") or {})
        messages = status.get("messages", [])
        completed = status.get("completed", False)
        status_str = status.get("status_str")  # "success" / "error"

        if entry and (completed or status_str in ("success", "error")):
            files = _collect_output_files(entry.get("outputs", {}))
            return {
                "status": "error" if status_str == "error" else "completed",
                "outputs": entry.get("outputs", {}),
                "messages": messages,
                "files": files,
                "raw": entry,
            }

        if on_tick:
            on_tick(int(time.time() - start), status_str, messages)

        if time.time() - start > max_wait:
            return {"status": "timeout", "outputs": entry.get("outputs", {}),
                    "messages": messages, "files": _collect_output_files(entry.get("outputs", {})),
                    "raw": entry}
        time.sleep(poll_every)


def _collect_output_files(outputs):
    """Extrai nomes de arquivos (images/gifs/videos) de um dict de outputs."""
    files = []
    for node_id, out in (outputs or {}).items():
        for key in ("images", "gifs", "videos", "audio"):
            for item in (out.get(key, []) or []):
                fn = item.get("filename")
                if fn:
                    files.append(fn)
    return files
