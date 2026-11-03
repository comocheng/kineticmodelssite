// The contribution routes at the bottom of the home page hero (database/templates/database/home.html).
//
// The routes are tabs. A terminal route types the commands of its steps, one step after the
// other, and its step list marks the step on screen; a click on a step types that step. The words
// and commands come from database/content/landing.yaml through the "lp-contribute-routes" JSON.
// Without JavaScript the page shows every route in full. With reduced motion a terminal shows
// its text at once, and a click on a step scrolls the terminal to it.

(() => {
    const root = document.getElementById("contribute");
    const data = document.getElementById("lp-contribute-routes");
    if (!root || !data) return;

    const routes = JSON.parse(data.textContent);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const tabs = [...root.querySelectorAll('[role="tab"]')];
    const panels = [...root.querySelectorAll('[role="tabpanel"]')];

    const CHAR_MS = 24;       // typing speed of a command
    const COMMAND_MS = 2600;  // the longest time to type one command, however long it is
    const LINE_MS = 160;      // before each output line
    const STEP_MS = 1100;     // pause after a step

    const escape = (text) => text.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
    // Text in angle brackets, such as <fuel>, is for the contributor to replace
    const marked = (text) => escape(text).replace(/&lt;[^&\n]*?&gt;/g, (m) => `<span class="lp-terminal__fill">${m}</span>`);
    const prompt = '<span class="lp-terminal__prompt">$ </span>';
    const caret = '<span class="lp-terminal__caret"></span>';

    function terminal(panel, route) {
        const screen = panel.querySelector(".lp-terminal__screen");
        const code = screen.querySelector("code");
        const steps = [...panel.querySelectorAll(".lp-contribute__step")];
        const copy = panel.querySelector('[data-action="copy"]');
        const replay = panel.querySelector('[data-action="replay"]');
        // Each step is a comment with its number and title, its commands, then their output
        const blocks = route.steps.map((step, i) => [
            { kind: "comment", step: i, text: `# ${String(i + 1).padStart(2, "0")} ${step.title}` },
            ...(step.commands || []).map((text) => ({ kind: "command", text })),
            ...(step.output || []).map((text) => ({ kind: text.startsWith("#") ? "comment" : "out", text })),
        ]);
        let run = 0;  // each play takes a new number, and an older play stops when it sees it
        let current = 0;

        const line = (item, length = item.text.length) => {
            const text = item.text.slice(0, length);
            if (item.kind === "command") return prompt + marked(text);
            const step = item.step === undefined ? "" : ` data-step="${item.step}"`;
            return `<span class="lp-terminal__${item.kind}"${step}>${marked(text)}</span>`;
        };
        const draw = (lines, live) => {
            code.innerHTML = lines.join("\n") + (live === undefined ? "" : (lines.length ? "\n" : "") + live + caret);
            screen.scrollTop = screen.scrollHeight;
        };
        const mark = (index) => {
            current = index;
            steps.forEach((item, i) => item.classList.toggle("is-current", i === index));
        };
        const wait = (ms, token) => new Promise((resolve) => setTimeout(() => resolve(token === run), ms));

        async function play(from = 0) {
            const token = ++run;
            replay.hidden = true;
            screen.setAttribute("aria-busy", "true");
            const lines = [];
            if (reduce.matches) {
                blocks.forEach((block, s) => {
                    block.forEach((item) => lines.push(line(item)));
                    if (s < blocks.length - 1) lines.push("");
                });
                draw(lines, prompt);
                mark(from);
                const heading = code.querySelector(`[data-step="${from}"]`);
                screen.scrollTop = from && heading ? heading.offsetTop - 18 : 0;
                screen.setAttribute("aria-busy", "false");
                return;
            }
            // The steps before the chosen one appear at once
            blocks.slice(0, from).forEach((block) => {
                block.forEach((item) => lines.push(line(item)));
                lines.push("");
            });
            for (let s = from; s < blocks.length; s++) {
                mark(s);
                for (const item of blocks[s]) {
                    if (item.kind === "command") {
                        const delay = Math.min(CHAR_MS, COMMAND_MS / item.text.length);
                        for (let n = 1; n <= item.text.length; n++) {
                            draw(lines, line(item, n));
                            if (!(await wait(delay, token))) return;
                        }
                    } else if (!(await wait(LINE_MS, token))) {
                        return;
                    }
                    lines.push(line(item));
                    draw(lines, prompt);
                }
                if (s < blocks.length - 1) {
                    lines.push("");
                    if (!(await wait(STEP_MS, token))) return;
                }
            }
            draw(lines, prompt);
            replay.hidden = false;
            screen.setAttribute("aria-busy", "false");
        }

        steps.forEach((item, i) => {
            item.querySelector("button")?.addEventListener("click", () => play(i));
        });
        replay.addEventListener("click", () => play(0));
        copy.hidden = false;
        copy.addEventListener("click", async () => {
            const text = (route.steps[current].commands || []).join("\n");
            try {
                await navigator.clipboard.writeText(text);
            } catch {
                // No clipboard access outside https: copy through a hidden field
                const field = Object.assign(document.createElement("textarea"), { value: text });
                document.body.append(field);
                field.select();
                document.execCommand("copy");
                field.remove();
            }
            copy.textContent = "Copied";
            setTimeout(() => { copy.textContent = "Copy step"; }, 1600);
        });

        draw([], prompt);
        mark(0);
        return { play, stop: () => { run += 1; } };
    }

    const players = panels.map((panel, i) => (panel.dataset.kind === "terminal" ? terminal(panel, routes[i]) : null));
    let visible = false;

    function select(index, focus = false) {
        tabs.forEach((tab, i) => {
            const on = i === index;
            tab.setAttribute("aria-selected", String(on));
            tab.tabIndex = on ? 0 : -1;
            panels[i].hidden = !on;
            if (!on) players[i]?.stop();
        });
        if (focus) tabs[index].focus();
        if (visible) players[index]?.play(0);
    }

    tabs.forEach((tab, i) => {
        tab.addEventListener("click", () => select(i));
        tab.addEventListener("keydown", (event) => {
            const keys = { ArrowDown: 1, ArrowRight: 1, ArrowUp: -1, ArrowLeft: -1 };
            let next = null;
            if (event.key in keys) next = (i + keys[event.key] + tabs.length) % tabs.length;
            if (event.key === "Home") next = 0;
            if (event.key === "End") next = tabs.length - 1;
            if (next === null) return;
            event.preventDefault();
            select(next, true);
        });
    });

    root.classList.add("is-enhanced");
    select(0);

    // Type the first terminal when the band comes into view, not while the visitor reads the hero
    const start = () => {
        if (visible) return;
        visible = true;
        const index = tabs.findIndex((tab) => tab.getAttribute("aria-selected") === "true");
        players[index]?.play(0);
    };
    if ("IntersectionObserver" in window) {
        const observer = new IntersectionObserver((entries) => {
            if (entries.some((entry) => entry.isIntersecting)) {
                observer.disconnect();
                start();
            }
        }, { threshold: 0.35 });
        observer.observe(root.querySelector(".lp-contribute__body"));
    } else {
        start();
    }
})();
