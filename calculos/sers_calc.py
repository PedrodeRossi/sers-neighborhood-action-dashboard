"""
SERS — Neighborhood Action Dashboard
Memorial de cálculo energético da Praça Comunitária Iluminada.

Lê  data/premissas.json
Gera data/resultados.json, data/resultados_mensais.csv,
     data/telemetria_simulada.csv e dashboard/dados.js

Uso:  python calculos/sers_calc.py

Fórmula base (enunciado 4.2):  E [kWh] = P [W] x t [h] / 1000
"""
import csv
import json
import math
import random
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
DASH = RAIZ / "dashboard"


def energia_kwh(p_w, horas):
    """E = P x t / 1000"""
    return p_w * horas / 1000


def horas_equivalentes(horas_noite, dim, dimeriza):
    """Horas equivalentes a 100% de potência numa noite.
    Sem dimerização: a noite inteira a 100%.
    Com dimerização: 'horas_100pct' a 100% e o restante a 'nivel_madrugada'."""
    if not dimeriza:
        return horas_noite
    h_cheia = min(dim["horas_100pct"], horas_noite)
    return h_cheia + dim["nivel_madrugada"] * (horas_noite - h_cheia)


def calcular(p):
    m = p["mensal"]
    eco = p["economico"]
    dim = p["dimerizacao"]
    alt = p["alternativas"]
    n = p["local"]["pontos_iluminacao"]
    tarifa = eco["tarifa_r_kwh"]
    fe = eco["fator_emissao_kgco2_kwh"]
    anos = eco["horizonte_anos"]

    a0, a1, a2, a3 = alt["A0"], alt["A1"], alt["A2"], alt["A3"]
    p_a0 = a0["potencia_lampada_w"] * (1 + a0["perdas_reator"])  # W por ponto (lâmpada + reator)

    mensal = []
    for i, mes in enumerate(m["meses"]):
        d, hn, hsp = m["dias"][i], m["horas_noite"][i], m["hsp_kwh_m2_dia"][i]
        # A0 — VSAP a 100% a noite toda
        e_a0 = n * energia_kwh(p_a0, hn) * d
        # A1 — LED com dimerização
        heq = horas_equivalentes(hn, dim, True)
        e_a1 = n * energia_kwh(a1["potencia_w"], heq) * d
        # A2 — solar off-grid: carga diária por poste x geração diária do módulo
        carga_dia_wh = a2["potencia_w"] * heq
        geracao_dia_wh = a2["painel_wp"] * hsp * a2["performance_ratio"]
        e_a2_carga = n * carga_dia_wh * d / 1000
        mensal.append({
            "mes": mes,
            "dias": d,
            "horas_noite": hn,
            "hsp": hsp,
            "horas_equivalentes_led": round(heq, 3),
            "A0_kwh": e_a0,
            "A1_kwh": e_a1,
            "A2_carga_kwh": e_a2_carga,
            "A2_carga_dia_wh_por_poste": carga_dia_wh,
            "A2_geracao_dia_wh_por_poste": geracao_dia_wh,
            "A2_margem_solar": geracao_dia_wh / carga_dia_wh,
        })

    # A3 — dimensionamento do FV on-grid para cobrir o consumo anual do A1
    e_a1_ano = sum(x["A1_kwh"] for x in mensal)
    hsp_dias = sum(x["hsp"] * x["dias"] for x in mensal)  # kWh/m² no ano (≈ kWh/kWp antes de perdas)
    kwp_necessario = e_a1_ano / (hsp_dias * a3["performance_ratio"])
    n_modulos = math.ceil(kwp_necessario * 1000 / a3["potencia_modulo_wp"])
    kwp = n_modulos * a3["potencia_modulo_wp"] / 1000
    for x in mensal:
        ger = kwp * x["hsp"] * x["dias"] * a3["performance_ratio"]
        x["A3_geracao_kwh"] = ger
        x["A3_consumo_kwh"] = x["A1_kwh"]
    # Compensação é anual (créditos valem 60 meses): rede líquida no ano
    ger_ano = sum(x["A3_geracao_kwh"] for x in mensal)

    # ---- Resumo anual por alternativa ----
    e_a0_ano = sum(x["A0_kwh"] for x in mensal)
    e_a2_ano = sum(x["A2_carga_kwh"] for x in mensal)
    compensado = min(ger_ano, e_a1_ano)
    rede_a3_ano = e_a1_ano - compensado  # energia ainda comprada
    custo_energia_a3_ano = rede_a3_ano * tarifa + compensado * tarifa * a3["parcela_nao_compensada"]

    capex = {
        "A0": 0,
        "A1": n * a1["capex_por_ponto"],
        "A2": n * a2["capex_por_ponto"],
        "A3": n * a1["capex_por_ponto"] + kwp * a3["custo_fv_r_kwp"],
    }
    capex_fv_a3 = kwp * a3["custo_fv_r_kwp"]
    manut_ano = {
        "A0": n * a0["manutencao_por_ponto_ano"],
        "A1": n * a1["manutencao_por_ponto_ano"],
        "A2": n * a2["manutencao_por_ponto_ano"],
        "A3": n * a1["manutencao_por_ponto_ano"] + capex_fv_a3 * a3["manutencao_fv_pct_capex_ano"],
    }
    rede_kwh_ano = {"A0": e_a0_ano, "A1": e_a1_ano, "A2": 0.0, "A3": rede_a3_ano}
    custo_energia_ano = {
        "A0": e_a0_ano * tarifa,
        "A1": e_a1_ano * tarifa,
        "A2": 0.0,
        "A3": custo_energia_a3_ano,
    }
    renovavel_kwh_ano = {"A0": 0.0, "A1": 0.0, "A2": e_a2_ano, "A3": compensado}
    consumo_total_ano = {"A0": e_a0_ano, "A1": e_a1_ano, "A2": e_a2_ano, "A3": e_a1_ano}

    resumo = {}
    for k in ["A0", "A1", "A2", "A3"]:
        opex = custo_energia_ano[k] + manut_ano[k]
        extra = 0.0
        if k == "A2" and a2["troca_bateria_ano"] <= anos:
            extra = n * a2["custo_bateria"]
        tco = capex[k] + opex * anos + extra
        economia_anual = (custo_energia_ano["A0"] + manut_ano["A0"]) - opex
        payback = capex[k] / economia_anual if k != "A0" and economia_anual > 0 else None
        co2_evitado = (e_a0_ano - rede_kwh_ano[k]) * fe
        resumo[k] = {
            "nome": alt[k]["nome"],
            "curto": alt[k]["curto"],
            "renovavel": alt[k]["renovavel"],
            "consumo_total_kwh_ano": consumo_total_ano[k],
            "consumo_rede_kwh_ano": rede_kwh_ano[k],
            "consumo_rede_kwh_mes": rede_kwh_ano[k] / 12,
            "economia_rede_kwh_mes": (e_a0_ano - rede_kwh_ano[k]) / 12,
            "economia_rede_pct": (e_a0_ano - rede_kwh_ano[k]) / e_a0_ano * 100,
            "participacao_renovavel_pct": renovavel_kwh_ano[k] / consumo_total_ano[k] * 100,
            "custo_energia_r_ano": custo_energia_ano[k],
            "manutencao_r_ano": manut_ano[k],
            "opex_r_mes": opex / 12,
            "reducao_custo_r_mes": economia_anual / 12,
            "capex_r": capex[k],
            "custos_extras_r": extra,
            "tco_r": tco,
            "payback_anos": payback,
            "co2_evitado_kg_ano": co2_evitado,
            "horas_eficientes_dia": 0.0 if k == "A0" else
                sum((x["horas_noite"] - dim["horas_100pct"]) * x["dias"] for x in mensal) / 365,
        }

    # ---- Verificação off-grid (A2) ----
    pior = min(mensal, key=lambda x: x["A2_margem_solar"])
    usable = a2["bateria_wh"] * a2["profundidade_descarga"]
    off = {
        "pior_mes": pior["mes"],
        "margem_pior_mes": pior["A2_margem_solar"],
        "carga_dia_pior_mes_wh": pior["A2_carga_dia_wh_por_poste"],
        "geracao_dia_pior_mes_wh": pior["A2_geracao_dia_wh_por_poste"],
        "autonomia_dias": usable / max(x["A2_carga_dia_wh_por_poste"] for x in mensal),
        "painel_minimo_wp": pior["A2_carga_dia_wh_por_poste"] / (pior["hsp"] * a2["performance_ratio"]),
        "atende": pior["A2_margem_solar"] >= 1.0,
    }
    fv = {
        "kwp_necessario": kwp_necessario,
        "n_modulos": n_modulos,
        "kwp_instalado": kwp,
        "geracao_kwh_ano": ger_ano,
        "area_aprox_m2": n_modulos * 2.6,
        "capex_fv_r": capex_fv_a3,
    }

    # ---- Matriz de decisão (0–5) ----
    md = p["matriz_decisao"]
    tcos = {k: resumo[k]["tco_r"] for k in resumo}
    econ = {k: resumo[k]["economia_rede_pct"] for k in resumo}
    tmin, tmax = min(tcos.values()), max(tcos.values())
    matriz = {}
    for k in resumo:
        notas = dict(md["notas_qualitativas"][k])
        notas["custo"] = 1 + 4 * (tmax - tcos[k]) / (tmax - tmin)
        notas["energia"] = 1 + 4 * econ[k] / 100
        total = sum(c["peso"] * notas[c["id"]] for c in md["criterios"])
        matriz[k] = {"notas": notas, "total": total}

    return {"mensal": mensal, "resumo": resumo, "offgrid": off, "fv_ongrid": fv,
            "matriz": matriz, "pot_a0_w": p_a0}


def telemetria_simulada(p, r, dias=30, semente=42):
    """Série diária simulada como se viesse dos nós de telegestão (A1/A3)
    para alimentar o painel de monitoramento. Variação por eventos de presença
    (fins de semana com mais uso) e falhas pontuais."""
    random.seed(semente)
    n = p["local"]["pontos_iluminacao"]
    nov = r["mensal"][10]
    base_a0 = nov["A0_kwh"] / nov["dias"]
    linhas = []
    for dia in range(1, dias + 1):
        fds = (dia + 5) % 7 in (5, 6)  # 2026-11-01 é domingo
        nivel = p["dimerizacao"]["nivel_madrugada"] + (0.08 if fds else 0.0) + random.uniform(-0.05, 0.05)
        h_cheia = p["dimerizacao"]["horas_100pct"]
        heq = h_cheia + nivel * (nov["horas_noite"] - h_cheia)
        ativos = n - (1 if random.random() < 0.1 else 0)
        kwh = ativos * p["alternativas"]["A1"]["potencia_w"] * heq / 1000
        eventos = int(random.gauss(220 if fds else 140, 25))
        linhas.append({
            "data": f"2026-11-{dia:02d}",
            "kwh_led_medido": round(kwh, 2),
            "kwh_vsap_referencia": round(base_a0, 2),
            "pontos_ativos": ativos,
            "eventos_presenca": eventos,
            "nivel_medio_madrugada_pct": round(nivel * 100, 1),
        })
    return linhas


def main():
    p = json.loads((DATA / "premissas.json").read_text(encoding="utf-8"))
    r = calcular(p)
    tel = telemetria_simulada(p, r)

    (DATA / "resultados.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    with open(DATA / "resultados_mensais.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(r["mensal"][0].keys()))
        w.writeheader()
        for x in r["mensal"]:
            w.writerow({k: (round(v, 2) if isinstance(v, float) else v) for k, v in x.items()})
    with open(DATA / "telemetria_simulada.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(tel[0].keys()))
        w.writeheader()
        w.writerows(tel)
    DASH.mkdir(exist_ok=True)
    (DASH / "dados.js").write_text(
        "// Arquivo gerado por calculos/sers_calc.py — não editar à mão.\n"
        "window.SERS_DADOS = " + json.dumps({"premissas": p, "resultados": r, "telemetria": tel},
                                             ensure_ascii=False) + ";\n",
        encoding="utf-8")

    # Saída resumida no terminal
    print(f"Potência por ponto VSAP (lâmpada + reator): {r['pot_a0_w']:.1f} W")
    print(f"{'Alt':4} {'Rede kWh/mês':>13} {'Econ %':>7} {'Renov %':>8} {'R$/mês red.':>12} "
          f"{'CAPEX R$':>10} {'TCO10 R$':>10} {'Payback':>8} {'CO2 kg/ano':>11} {'Matriz':>7}")
    for k, v in r["resumo"].items():
        pb = f"{v['payback_anos']:.1f}" if v["payback_anos"] else "-"
        print(f"{k:4} {v['consumo_rede_kwh_mes']:13.0f} {v['economia_rede_pct']:7.1f} "
              f"{v['participacao_renovavel_pct']:8.0f} {v['reducao_custo_r_mes']:12.0f} {v['capex_r']:10.0f} "
              f"{v['tco_r']:10.0f} {pb:>8} {v['co2_evitado_kg_ano']:11.0f} {r['matriz'][k]['total']:7.2f}")
    o = r["offgrid"]
    print(f"Off-grid: pior mês {o['pior_mes']} margem {o['margem_pior_mes']:.2f}, "
          f"autonomia {o['autonomia_dias']:.1f} dias, painel mínimo {o['painel_minimo_wp']:.0f} Wp")
    fv = r["fv_ongrid"]
    print(f"FV on-grid: {fv['n_modulos']} módulos = {fv['kwp_instalado']:.2f} kWp, "
          f"{fv['geracao_kwh_ano']:.0f} kWh/ano, ~{fv['area_aprox_m2']:.0f} m²")


if __name__ == "__main__":
    main()
