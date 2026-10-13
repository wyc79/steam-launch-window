// The events lanes, shared by Competition ahead and Typical for this time of year:
// an "Events" label, a lane per kind, then a rule. Each event is a block over the
// weeks it covers, its name from its first week up to the next event in the lane
// (cut short with an ellipsis there). The items sit in the caller's CSS grid: rows
// from `first` (--tr), weeks from column 2 (--from, --to). Drawn for the eye; the
// events are also said in each week's label.

import { eventText, formatDate } from "../heatview.js";
import { h } from "./dom.js";

// band: bandEvents' result. fit: names stay inside their own block (narrow weeks),
// cut short with an ellipsis; the full name is in the title.
export function laneItems(band, first, s, { fit = false } = {}) {
  const a = s.ahead;
  if (!band.lanes.length) return [];
  const out = [h("div", { class: "hm-band-label", style: `--tr:${first}` }, a.eventsLabel)];
  band.lanes.forEach((lane, i) => {
    const tr = first + 1 + i;
    out.push(h("div", { class: "hm-lane-name", style: `--tr:${tr}` }, lane.row === 0 ? a.kinds[lane.kind] : ""));
    for (const e of band.events.filter((x) => x.lane === i)) {
      const full = `${eventText(e, s)}, ${a.eventDates(formatDate(e.start, s), formatDate(e.end, s))}`;
      const end = fit ? e.weeks[1] + 1 : e.room; // where the name may run to (a week index)
      out.push(
        h("div", {
          class: `hm-block is-${e.kind}`,
          style: `--tr:${tr};--from:${e.weeks[0] + 2};--to:${e.weeks[1] + 3}`,
        }),
        h(
          "div",
          { class: "hm-block-name", style: `--tr:${tr};--from:${e.weeks[0] + 2};--to:${end + 2}`, title: full },
          eventText({ ...e, name: e.short }, s),
        ),
      );
    }
  });
  out.push(h("div", { class: "hm-band-rule", style: `--tr:${first + 1 + band.lanes.length}` }));
  return out;
}
