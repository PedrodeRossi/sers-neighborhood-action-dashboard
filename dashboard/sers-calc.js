/*
 * SERS — componente de cálculo do Neighborhood Action Dashboard.
 * Porta em JavaScript de calculos/sers_calc.py (mesmas fórmulas), usada para
 * recalcular os indicadores quando o usuário altera premissas no dashboard.
 * E [kWh] = P [W] x t [h] / 1000
 */
(function (global) {
  "use strict";

  function energiaKwh(pW, horas) { return pW * horas / 1000; }

  function horasEquivalentes(horasNoite, dim, dimeriza) {
    if (!dimeriza) return horasNoite;
    var hCheia = Math.min(dim.horas_100pct, horasNoite);
    return hCheia + dim.nivel_madrugada * (horasNoite - hCheia);
  }

  function sum(arr, f) { return arr.reduce(function (s, x) { return s + f(x); }, 0); }

  function calcular(p) {
    var m = p.mensal, eco = p.economico, dim = p.dimerizacao, alt = p.alternativas;
    var n = p.local.pontos_iluminacao, tarifa = eco.tarifa_r_kwh;
    var fe = eco.fator_emissao_kgco2_kwh, anos = eco.horizonte_anos;
    var a0 = alt.A0, a1 = alt.A1, a2 = alt.A2, a3 = alt.A3;
    var pA0 = a0.potencia_lampada_w * (1 + a0.perdas_reator);

    var mensal = m.meses.map(function (mes, i) {
      var d = m.dias[i], hn = m.horas_noite[i], hsp = m.hsp_kwh_m2_dia[i];
      var heq = horasEquivalentes(hn, dim, true);
      var cargaDia = a2.potencia_w * heq;
      var gerDia = a2.painel_wp * hsp * a2.performance_ratio;
      return {
        mes: mes, dias: d, horas_noite: hn, hsp: hsp, horas_equivalentes_led: heq,
        A0_kwh: n * energiaKwh(pA0, hn) * d,
        A1_kwh: n * energiaKwh(a1.potencia_w, heq) * d,
        A2_carga_kwh: n * cargaDia * d / 1000,
        A2_carga_dia_wh_por_poste: cargaDia,
        A2_geracao_dia_wh_por_poste: gerDia,
        A2_margem_solar: gerDia / cargaDia
      };
    });

    var eA1 = sum(mensal, function (x) { return x.A1_kwh; });
    var hspDias = sum(mensal, function (x) { return x.hsp * x.dias; });
    var kwpNec = eA1 / (hspDias * a3.performance_ratio);
    var nMod = Math.ceil(kwpNec * 1000 / a3.potencia_modulo_wp);
    var kwp = nMod * a3.potencia_modulo_wp / 1000;
    mensal.forEach(function (x) {
      x.A3_geracao_kwh = kwp * x.hsp * x.dias * a3.performance_ratio;
      x.A3_consumo_kwh = x.A1_kwh;
    });
    var gerAno = sum(mensal, function (x) { return x.A3_geracao_kwh; });

    var eA0 = sum(mensal, function (x) { return x.A0_kwh; });
    var eA2 = sum(mensal, function (x) { return x.A2_carga_kwh; });
    var compensado = Math.min(gerAno, eA1);
    var redeA3 = eA1 - compensado;
    var capexFv = kwp * a3.custo_fv_r_kwp;

    var capex = { A0: 0, A1: n * a1.capex_por_ponto, A2: n * a2.capex_por_ponto, A3: n * a1.capex_por_ponto + capexFv };
    var manut = { A0: n * a0.manutencao_por_ponto_ano, A1: n * a1.manutencao_por_ponto_ano,
      A2: n * a2.manutencao_por_ponto_ano, A3: n * a1.manutencao_por_ponto_ano + capexFv * a3.manutencao_fv_pct_capex_ano };
    var rede = { A0: eA0, A1: eA1, A2: 0, A3: redeA3 };
    var custoE = { A0: eA0 * tarifa, A1: eA1 * tarifa, A2: 0,
      A3: redeA3 * tarifa + compensado * tarifa * a3.parcela_nao_compensada };
    var renov = { A0: 0, A1: 0, A2: eA2, A3: compensado };
    var total = { A0: eA0, A1: eA1, A2: eA2, A3: eA1 };
    var horasEf = sum(mensal, function (x) { return (x.horas_noite - dim.horas_100pct) * x.dias; }) / 365;

    var resumo = {};
    ["A0", "A1", "A2", "A3"].forEach(function (k) {
      var opex = custoE[k] + manut[k];
      var extra = (k === "A2" && a2.troca_bateria_ano <= anos) ? n * a2.custo_bateria : 0;
      var econAnual = (custoE.A0 + manut.A0) - opex;
      resumo[k] = {
        nome: alt[k].nome, curto: alt[k].curto, renovavel: alt[k].renovavel,
        consumo_total_kwh_ano: total[k],
        consumo_rede_kwh_ano: rede[k],
        consumo_rede_kwh_mes: rede[k] / 12,
        economia_rede_kwh_mes: (eA0 - rede[k]) / 12,
        economia_rede_pct: (eA0 - rede[k]) / eA0 * 100,
        participacao_renovavel_pct: renov[k] / total[k] * 100,
        custo_energia_r_ano: custoE[k],
        manutencao_r_ano: manut[k],
        opex_r_mes: opex / 12,
        reducao_custo_r_mes: econAnual / 12,
        capex_r: capex[k],
        custos_extras_r: extra,
        tco_r: capex[k] + opex * anos + extra,
        payback_anos: (k !== "A0" && econAnual > 0) ? capex[k] / econAnual : null,
        co2_evitado_kg_ano: (eA0 - rede[k]) * fe,
        horas_eficientes_dia: k === "A0" ? 0 : horasEf
      };
    });

    var pior = mensal.reduce(function (a, b) { return b.A2_margem_solar < a.A2_margem_solar ? b : a; });
    var maxCarga = Math.max.apply(null, mensal.map(function (x) { return x.A2_carga_dia_wh_por_poste; }));
    var offgrid = {
      pior_mes: pior.mes, margem_pior_mes: pior.A2_margem_solar,
      carga_dia_pior_mes_wh: pior.A2_carga_dia_wh_por_poste,
      geracao_dia_pior_mes_wh: pior.A2_geracao_dia_wh_por_poste,
      autonomia_dias: a2.bateria_wh * a2.profundidade_descarga / maxCarga,
      painel_minimo_wp: pior.A2_carga_dia_wh_por_poste / (pior.hsp * a2.performance_ratio),
      atende: pior.A2_margem_solar >= 1
    };
    var fv = { kwp_necessario: kwpNec, n_modulos: nMod, kwp_instalado: kwp, geracao_kwh_ano: gerAno,
      area_aprox_m2: nMod * 2.6, capex_fv_r: capexFv };

    var md = p.matriz_decisao;
    var ks = Object.keys(resumo);
    var tcos = ks.map(function (k) { return resumo[k].tco_r; });
    var tmin = Math.min.apply(null, tcos), tmax = Math.max.apply(null, tcos);
    var matriz = {};
    ks.forEach(function (k) {
      var notas = Object.assign({}, md.notas_qualitativas[k]);
      notas.custo = tmax === tmin ? 5 : 1 + 4 * (tmax - resumo[k].tco_r) / (tmax - tmin);
      notas.energia = 1 + 4 * resumo[k].economia_rede_pct / 100;
      matriz[k] = { notas: notas, total: sum(md.criterios, function (c) { return c.peso * notas[c.id]; }) };
    });

    return { mensal: mensal, resumo: resumo, offgrid: offgrid, fv_ongrid: fv, matriz: matriz, pot_a0_w: pA0 };
  }

  global.SERSCalc = { calcular: calcular, energiaKwh: energiaKwh, horasEquivalentes: horasEquivalentes };
})(typeof window !== "undefined" ? window : this);
