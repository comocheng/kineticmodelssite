/* Interactive thermo and rate-coefficient plots (Plotly).
 * Data comes from json_script tags built in database/services/curves.py. Labels are model and
 * source names, so they are inserted with textContent, never as HTML. */
(function () {
    "use strict";

    // Validated categorical order (dataviz reference palette); never cycled past eight.
    const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"];
    const OTHER = "#898781";
    const INK = "#52514e";
    const GRID = "#e1e0d9";
    const AXIS = "#c3c2b7";
    // A source keeps its colour on every page; model thermo takes the remaining slots.
    const SOURCE_COLOR = {
        atct: SERIES[0], atct_constrained: SERIES[0], burcat: SERIES[1],
        group_additivity: SERIES[2], rmg_thermo_library: SERIES[3],
    };
    const MODEL_SLOTS = SERIES.slice(4);
    const RECORD_INK = "#1f2933";
    const RECORD_DASH = {rmg_library: "dash", rmg_family: "dot"};
    const QUANTITY = {
        Cp: {title: "C<sub>p</sub> (J mol⁻¹ K⁻¹)", unit: "J/(mol K)"},
        H: {title: "H (kJ mol⁻¹)", unit: "kJ/mol"},
        S: {title: "S (J mol⁻¹ K⁻¹)", unit: "J/(mol K)"},
        G: {title: "G (kJ mol⁻¹)", unit: "kJ/mol"},
    };
    const CONFIG = {responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"]};

    function readData(id) {
        const element = document.getElementById(id);
        return element ? JSON.parse(element.textContent) : null;
    }

    function layout(xTitle, yTitle, traceCount, extra) {
        const axis = {gridcolor: GRID, linecolor: AXIS, zeroline: false, tickfont: {color: INK}, ticks: "outside", tickcolor: AXIS};
        return Object.assign({
            margin: {l: 70, r: 20, t: 10, b: 55},
            font: {family: "system-ui, -apple-system, 'Segoe UI', sans-serif", size: 13, color: INK},
            paper_bgcolor: "#ffffff", plot_bgcolor: "#ffffff",
            // One readout with every series when it stays short; otherwise the nearest line.
            hovermode: traceCount <= 10 ? "x unified" : "closest",
            // Above the plot: it can never collide with the axis title, and Plotly makes room.
            legend: {orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: {size: 12}},
            xaxis: Object.assign({title: {text: xTitle}, showspikes: true, spikemode: "across", spikethickness: 1, spikecolor: AXIS}, axis),
            yaxis: Object.assign({title: {text: yTitle}}, axis),
        }, extra || {});
    }

    function interpolate(xs, ys, x) {
        for (let i = 0; i < xs.length - 1; i++) {
            const lo = Math.min(xs[i], xs[i + 1]), hi = Math.max(xs[i], xs[i + 1]);
            if (x >= lo && x <= hi && ys[i] != null && ys[i + 1] != null) {
                const t = xs[i + 1] === xs[i] ? 0 : (x - xs[i]) / (xs[i + 1] - xs[i]);
                return ys[i] + t * (ys[i + 1] - ys[i]);
            }
        }
        return null;
    }

    function renderTable(container, columns, rows) {
        container.replaceChildren();
        const table = document.createElement("table");
        table.className = "table table-sm small mb-0";
        const head = table.createTHead().insertRow();
        ["Source", ...columns].forEach(function (text) {
            const cell = document.createElement("th");
            cell.textContent = text;
            head.appendChild(cell);
        });
        const body = table.createTBody();
        rows.forEach(function (row) {
            const tr = body.insertRow();
            row.forEach(function (value, i) {
                const cell = tr.insertCell();
                if (i === 0 && value && typeof value === "object") {
                    sourceCell(cell, value);
                    return;
                }
                cell.textContent = value == null ? "–" : (i === 0 ? value : Number(value).toPrecision(5));
                if (i > 0) cell.className = "text-end font-monospace";
            });
        });
        container.appendChild(table);
    }

    function anchor(text, url) {
        if (!url) return document.createTextNode(text);
        const a = document.createElement("a");
        a.href = url;
        a.textContent = text;
        if (/^https?:/.test(url)) { a.target = "_blank"; a.rel = "noopener noreferrer"; }
        return a;
    }

    // The table's Source cell: links to the models or libraries behind a curve, then to the
    // plotted rate or polynomial itself.
    function sourceCell(cell, source) {
        const links = source.links || [];
        if (!links.length) {
            cell.appendChild(anchor(source.label, source.url));
            return;
        }
        links.forEach(function (link, i) {
            if (i) cell.appendChild(document.createTextNode(", "));
            cell.appendChild(anchor(link.text, link.url));
        });
        if (source.url) {
            cell.appendChild(document.createTextNode(" · "));
            const data = anchor(source.dataText, source.url);
            data.className = "text-muted";
            cell.appendChild(data);
        }
    }

    function colorFor(curves) {
        let modelSlot = 0;
        return curves.map(function (curve) {
            if (curve.kind !== "model") return SOURCE_COLOR[curve.kind] || OTHER;
            return modelSlot < MODEL_SLOTS.length ? MODEL_SLOTS[modelSlot++] : OTHER;
        });
    }

    function legendFor(colors, otherName) {
        const others = colors.filter(function (c) { return c === OTHER; }).length;
        let first = true;
        return colors.map(function (color) {
            if (color !== OTHER) return {};
            const entry = {legendgroup: "other", showlegend: first, name: otherName + " (" + others + ")"};
            first = false;
            return entry;
        });
    }

    function hoverName(curve) {
        return curve.models && curve.models.length > 1 ? curve.models.join(", ") : curve.label;
    }

    window.renderThermoPlot = function (plotId, dataId, controlsId, tableId) {
        const data = readData(dataId);
        const plot = document.getElementById(plotId);
        if (!data || !plot || !data.curves.length) {
            if (plot) plot.closest("[data-plot-section]").hidden = true;
            return;
        }
        const colors = colorFor(data.curves);
        const legend = legendFor(colors, "Other model thermo");
        let quantity = "Cp";

        function draw() {
            const traces = data.curves.map(function (curve, i) {
                const other = colors[i] === OTHER;
                return Object.assign({
                    x: curve.T, y: curve[quantity], mode: "lines", name: curve.label,
                    line: {color: colors[i], width: other ? 1.5 : 2}, opacity: other ? 0.7 : 1,
                    hovertemplate: "%{y:.4g} " + QUANTITY[quantity].unit + "<extra>" + hoverName(curve).replace(/</g, "&lt;") + "</extra>",
                }, legend[i]);
            });
            data.points.filter(function (point) { return point[quantity]; }).forEach(function (point) {
                traces.push({
                    x: point.T, y: point[quantity], mode: "markers", name: point.label,
                    marker: {color: SOURCE_COLOR[point.kind] || OTHER, size: 9, line: {color: "#ffffff", width: 2}},
                    error_y: point.dH ? {type: "data", array: point.dH, color: SOURCE_COLOR[point.kind], thickness: 2, width: 6} : undefined,
                    hovertemplate: "%{y:.4g} " + QUANTITY[quantity].unit + " at %{x} K<extra>" + point.label.replace(/</g, "&lt;") + "</extra>",
                });
            });
            Plotly.react(plot, traces, layout("Temperature (K)", QUANTITY[quantity].title, traces.length), CONFIG);
            if (tableId) {
                const temps = data.table_temperatures;
                renderTable(document.getElementById(tableId), temps.map(function (t) { return t + " K"; }),
                    data.curves.map(function (curve) {
                        return [{label: curve.models && curve.models.length ? curve.models.join(", ") : curve.label,
                                 links: curve.links, url: curve.url, dataText: "polynomial"}]
                            .concat(temps.map(function (t) { return interpolate(curve.T, curve[quantity], t); }));
                    }));
            }
        }

        const controls = controlsId && document.getElementById(controlsId);
        if (controls) {
            controls.querySelectorAll("[data-quantity]").forEach(function (button) {
                button.addEventListener("click", function () {
                    quantity = button.dataset.quantity;
                    controls.querySelectorAll("[data-quantity]").forEach(function (b) {
                        b.classList.toggle("active", b === button);
                        b.setAttribute("aria-pressed", b === button ? "true" : "false");
                    });
                    draw();
                });
            });
        }
        draw();
    };

    window.renderRatePlot = function (plotId, dataId, pressureId, tableId) {
        const data = readData(dataId);
        const plot = document.getElementById(plotId);
        if (!data || !plot || !data.series.length) {
            if (plot) plot.closest("[data-plot-section]").hidden = true;
            return;
        }
        // Eight hues at most, for the models: past eight, the first seven keep theirs and the
        // rest fold to grey. RMG-database counterparts are dark and dashed, keyed by dash pattern.
        const modelCount = data.series.filter(function (s) { return s.kind === "model"; }).length;
        const colors = data.series.map(function (s, i) {
            if (s.kind !== "model") return RECORD_INK;
            return modelCount <= SERIES.length || i < SERIES.length - 1 ? SERIES[i] : OTHER;
        });
        const legend = legendFor(colors, "Other models");
        // Each kind of outside source gets one legend entry; hover still names every source.
        const SOURCE_NAME = {rmg_library: "RMG-database libraries", rmg_family: "RMG family rate-rule estimate"};
        const firstOfKind = {};
        data.series.forEach(function (s, i) {
            if (s.kind === "model") return;
            const count = data.series.filter(function (t) { return t.kind === s.kind; }).length;
            legend[i] = {legendgroup: s.kind, showlegend: !(s.kind in firstOfKind),
                         name: SOURCE_NAME[s.kind] + (count > 1 ? " (" + count + " distinct rates)" : "")};
            firstOfKind[s.kind] = true;
        });
        const select = pressureId && document.getElementById(pressureId);
        const anyPdep = data.series.some(function (s) { return s.pdep; });
        if (select) {
            // d-none, not hidden: Bootstrap's d-flex would override the hidden attribute.
            select.closest("[data-pressure-control]").classList.toggle("d-none", !anyPdep);
            data.pressures.forEach(function (p) {
                const option = document.createElement("option");
                option.value = String(p);
                option.textContent = p + " bar";
                option.selected = p === 1;
                select.appendChild(option);
            });
            select.addEventListener("change", draw);
        }

        function valuesAt(series) {
            const pressure = select && anyPdep ? select.value : "1.0";
            const key = series.pdep ? (series.k[pressure] ? pressure : String(series.pressures[0])) : "1.0";
            return series.k[key] || series.k[Object.keys(series.k)[0]];
        }

        function draw() {
            const traces = data.series.map(function (series, i) {
                const other = colors[i] === OTHER;
                return Object.assign({
                    x: series.x, y: valuesAt(series), customdata: series.T, mode: "lines", name: series.label,
                    line: {color: colors[i], width: other ? 1.5 : 2, dash: RECORD_DASH[series.kind] || "solid"},
                    opacity: other ? 0.7 : 1,
                    hovertemplate: "%{y:.3e} at %{customdata} K<extra>" + hoverName(series).replace(/</g, "&lt;") + "</extra>",
                }, legend[i]);
            });
            Plotly.react(plot, traces, layout("1000 / T (K⁻¹)", "k (" + data.units + ")", traces.length,
                {yaxis: {type: "log", exponentformat: "power", gridcolor: GRID, linecolor: AXIS, title: {text: "k (" + data.units + ")"}}}), CONFIG);
            if (tableId) {
                const temps = [500, 1000, 1500, 2000];
                renderTable(document.getElementById(tableId), temps.map(function (t) { return t + " K"; }),
                    data.series.map(function (series) {
                        const ys = valuesAt(series);
                        return [{label: series.models && series.models.length ? series.models.join(", ") : series.label,
                                 links: series.links, url: series.url, dataText: "rate"}]
                            .concat(temps.map(function (t) {
                                const logs = ys.map(function (y) { return y ? Math.log10(y) : null; });
                                const value = interpolate(series.x, logs, 1000 / t);
                                return value == null ? null : Math.pow(10, value);
                            }));
                    }));
            }
        }
        draw();
    };

    // One hue, light to dark (dataviz sequential blue); empty cells stay blank.
    const SEQUENTIAL = [[0, "#cde2fb"], [0.25, "#86b6ef"], [0.5, "#3987e5"], [0.75, "#1c5cab"], [1, "#0d366b"]];

    window.renderSimilarityHeatmap = function (plotId, dataId, compareUrl) {
        const data = readData(dataId);
        const plot = document.getElementById(plotId);
        if (!data || !plot || !data.names.length) {
            if (plot) plot.closest("[data-plot-section]").hidden = true;
            return;
        }
        const trace = {
            type: "heatmap", z: data.z, x: data.names, y: data.names, customdata: data.counts,
            colorscale: SEQUENTIAL, zmin: 0, zmax: 1, xgap: 1, ygap: 1, hoverongaps: false,
            colorbar: {title: {text: "identical", side: "right"}, tickformat: ".0%", thickness: 12},
            hovertemplate: "%{y}<br>rates identical in %{x}: %{z:.0%} (%{customdata})<extra></extra>",
        };
        const lay = layout("", "", 1, {
            margin: {l: 220, r: 20, t: 10, b: 200}, hovermode: "closest",
            xaxis: {tickangle: -60, tickfont: {size: 9}, showgrid: false, automargin: true},
            yaxis: {autorange: "reversed", tickfont: {size: 9}, showgrid: false, automargin: true},
        });
        Plotly.newPlot(plot, [trace], lay, CONFIG);
        plot.on("plotly_click", function (event) {
            const point = event.points && event.points[0];
            if (!point || point.z == null) return;
            const a = data.ids[point.pointIndex[0]], b = data.ids[point.pointIndex[1]];
            window.location.href = compareUrl + "?a=" + a + "&b=" + b;
        });
    };
})();
