// Presentation only: keep notes' search task and Pocket's plain-text history intact.
import { notify } from "./store.js";
import { copyText, html, Icon } from "./ui.js";

/** Recognize only complete tables produced by notes' common-food search task. */
export function foodSearchRows(output) {
    const [header, ...lines] = output.trim().split(/\r?\n/);
    const nutrition = /^id\s+name\s+serving\s+kcal\s+protein\s+carbs\s+fat\s+fiber$/.test(header);
    if (!nutrition && !/^id\s+name$/.test(header)) return null;
    const rows = [];
    for (const line of lines) {
        const match = /^([a-z0-9][a-z0-9._-]*)\s+(.+)$/i.exec(line);
        if (!match) return null;
        rows.push({ key: match[1], details: nutrition ? match[2] : null });
    }
    return { rows, heading: nutrition ? header.replace(/^id\s+/, "") : null };
}

export function FoodSearchCard({ entry, results }) {
    return html`<div class="shell-row" id=${`entry-${entry.id}`}>
        <div class="shell-card">
            <div class="shell-head">
                <span class="mono shell-command">/search</span>
                <span class="muted small">${entry.name} · not shown to Pi</span>
            </div>
            ${results.rows.length === 0 ? html`<span class="muted">No matching foods.</span>` : html`
                <div class="notes-food-search">
                    <table>
                        <thead><tr><th scope="col">Key</th>
                            ${results.heading && html`<th scope="col"><pre>${results.heading}</pre></th>`}
                        </tr></thead>
                        <tbody>${results.rows.map((row) => html`<tr key=${row.key}>
                            <td><div class="notes-food-key">
                                <code>${row.key}</code>
                                <button type="button" class="icon-btn" title=${`Copy ${row.key}`}
                                    aria-label=${`Copy ${row.key}`}
                                    onClick=${() => {
                                        // Call synchronously in the click gesture: HTTP uses execCommand,
                                        // and Safari must not lose user activation to an earlier await.
                                        copyText(row.key).then(
                                            () => notify("info", `Copied ${row.key}.`),
                                            () => notify("error", "Could not copy the key."),
                                        );
                                    }}><${Icon} name="copy" size=${16} /></button>
                            </div></td>
                            ${row.details !== null && html`<td><pre>${row.details}</pre></td>`}
                        </tr>`)}</tbody>
                    </table>
                </div>`}
        </div>
    </div>`;
}
