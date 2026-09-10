import { useEffect, useRef } from "react";
import Plotly from "plotly.js-dist-min";

export default function Chart({ title, figure, wide }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!ref.current || !figure) return;
    const el = ref.current;
    Plotly.react(el, figure.data, figure.layout, {
      responsive: true,
      displayModeBar: false,
    });
    const ro = new ResizeObserver(() => Plotly.Plots.resize(el));
    ro.observe(el);
    return () => {
      ro.disconnect();
      Plotly.purge(el);
    };
  }, [figure]);

  return (
    <div className={`chart${wide ? " wide" : ""}`}>
      <h3>{title}</h3>
      <div ref={ref} className="plot" />
    </div>
  );
}
