# Memorial de cálculo — Praça Comunitária Iluminada (SERS)

Todos os números abaixo são gerados por `python calculos/sers_calc.py` a partir de `data/premissas.json`. Unidades: W, h, kWh, R$, kg CO₂e. Período de referência: 1 ano (jan–dez); custos acumulados em 10 anos.

## 1. Fórmulas

| # | Grandeza | Fórmula |
|---|---|---|
| F1 | Energia de um equipamento | E [kWh] = P [W] × t [h] / 1000 |
| F2 | Potência VSAP com reator | P = 150 W × (1 + 0,12) = 168 W |
| F3 | Horas equivalentes com dimerização | h_eq = 5 h × 100% + (h_noite − 5 h) × 50% |
| F4 | Consumo mensal de N pontos | E_mês = N × P × h × dias / 1000 |
| F5 | Geração diária do painel off-grid | G = Wp × HSP × PR (PR = 0,75) |
| F6 | Potência FV on-grid necessária | kWp = E_ano / (Σ HSP×dias × PR), PR = 0,78 |
| F7 | Custo anual de energia | C = E_rede × tarifa (+ 15% × tarifa × E_compensada na A3) |
| F8 | Emissões evitadas | CO₂ = (E_A0 − E_rede) × 0,0385 kg/kWh |
| F9 | Custo total (TCO) 10 anos | Investimento + 10 × (energia + manutenção) + trocas |
| F10 | Payback simples | Investimento / (custo anual A0 − custo anual Ax) |

## 2. Exemplos de cálculo (junho — pior mês)

- **A0 (VSAP):** 30 × 168 W × 13,2 h × 30 dias / 1000 = **1.996 kWh**
- **A1 (LED 80 W):** h_eq = 5 + 0,5 × (13,2 − 5) = 9,1 h → 30 × 80 × 9,1 × 30 / 1000 = **655 kWh**
- **A2 (LED 60 W por poste):** carga diária = 60 × 9,1 = 546 Wh; geração = 250 Wp × 3,8 × 0,75 = 712,5 Wh → margem 1,30 (✔ atende). Painel mínimo = 546 / (3,8 × 0,75) = 192 Wp → adotado 250 Wp (folga para sujeira e degradação).
  Bateria: 1.280 Wh × 80% (profundidade de descarga) = 1.024 Wh úteis ÷ 546 Wh = **1,9 noites** de autonomia sem sol.
- **A3 (FV on-grid):** E_A1 anual = 7.455 kWh; Σ(HSP × dias) = 1.672 kWh/m²·ano; kWp = 7.455 / (1.672 × 0,78) = 5,72 kWp → **11 módulos de 550 Wp = 6,05 kWp** → geração 7.888 kWh/ano (≥ consumo).

## 3. Resultado mês a mês (kWh)

| Mês | Noite (h) | HSP | h_eq LED | A0 VSAP | A1 LED | A3 geração FV | A2 carga/poste (Wh/dia) | A2 geração/poste (Wh/dia) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Jan | 10,9 | 4,9 | 7,95 | 1.703 | 591 | 717 | 477 | 919 |
| Fev | 11,4 | 5,2 | 8,20 | 1.609 | 551 | 687 | 492 | 975 |
| Mar | 11,9 | 4,8 | 8,45 | 1.859 | 629 | 702 | 507 | 900 |
| Abr | 12,5 | 4,6 | 8,75 | 1.890 | 630 | 651 | 525 | 862 |
| Mai | 13,0 | 4,0 | 9,00 | 2.031 | 670 | 585 | 540 | 750 |
| Jun | 13,2 | 3,8 | 9,10 | 1.996 | 655 | 538 | 546 | 712 |
| Jul | 13,1 | 3,9 | 9,05 | 2.047 | 673 | 571 | 543 | 731 |
| Ago | 12,7 | 4,7 | 8,85 | 1.984 | 658 | 688 | 531 | 881 |
| Set | 12,1 | 4,5 | 8,55 | 1.830 | 616 | 637 | 513 | 844 |
| Out | 11,6 | 4,8 | 8,30 | 1.812 | 618 | 702 | 498 | 900 |
| Nov | 11,0 | 4,9 | 8,00 | 1.663 | 576 | 694 | 480 | 919 |
| Dez | 10,8 | 4,9 | 7,90 | 1.687 | 588 | 717 | 474 | 919 |
| **Ano** | média 12,0 | | | **22.111** | **7.455** | **7.888** | | |

De maio a julho a geração FV (A3) fica abaixo do consumo; os créditos acumulados nos outros meses cobrem a diferença (compensação anual).

## 4. Custos

| Item | A0 | A1 | A2 | A3 |
|---|---:|---:|---:|---:|
| Investimento | 0 | 30 × 1.950 = 58.500 | 30 × 4.500 = 135.000 | 58.500 + 6,05 × 3.800 = 81.490 |
| Energia (R$/ano) | 22.111 × 0,50 = 11.056 | 7.455 × 0,50 = 3.727 | 0 | 7.455 × 0,50 × 15% = 559 |
| Manutenção (R$/ano) | 30 × 150 = 4.500 | 30 × 40 = 1.200 | 30 × 120 = 3.600 | 1.200 + 1% × 22.990 = 1.430 |
| Trocas no horizonte | — | — | baterias ano 8: 30 × 1.800 = 54.000 | — |
| **TCO 10 anos** | **155.557** | **107.773** | **225.000** | **101.380** |
| Economia anual vs A0 | — | 10.629 | 11.956 | 13.567 |
| **Payback** | — | **5,5 anos** | **11,3 anos** | **6,0 anos** |

## 5. Emissões evitadas

- A1: (22.111 − 7.455) × 0,0385 = **564 kg CO₂e/ano**
- A2 e A3: 22.111 × 0,0385 = **851 kg CO₂e/ano**

(Não inclui emissões de fabricação dos equipamentos — ver limitações.)

## 6. Sensibilidade (testável no dashboard)

- Tarifa a R$ 0,80/kWh → payback da A3 cai para ~4 anos.
- Sem dimerização (LED a 100%) → consumo da A1 sobe de 621 para 876 kWh/mês.
- Fator de emissão de 0,10 kg/kWh (ano seco) → CO₂ evitado da A3 sobe para ~2,2 t/ano.
