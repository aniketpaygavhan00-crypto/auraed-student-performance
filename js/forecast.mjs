export function calculateForecast(inputs) {
  const scaledFeatures = [
    (inputs.studyHours - 4.2) / 2.0149441679609885,
    (inputs.attendance - 81.05) / 10.360863863597475,
    (inputs.percentage - 65.95) / 10.80034721664077,
  ];
  const score = Math.round(Math.max(0, Math.min(100,
    69.95
      + scaledFeatures[0] * 3.257689994970591
      + scaledFeatures[1] * 3.3485694904914016
      + scaledFeatures[2] * 5.769309147008137
  )));
  const passed = score >= 50;
  const status = score >= 75 ? "On track" : passed ? "Building momentum" : "Needs support";
  const headline = score >= 75
    ? "You’re building something great."
    : passed
      ? "You’re finding your rhythm."
      : "There’s room to grow from here.";
  const message = score >= 75
    ? "Strong habits are showing up in your forecast. Keep the rhythm going."
    : passed
      ? "You have a foundation to build on. A little more consistency can move the needle."
      : "A focused study plan and regular check-ins can help improve this outlook.";
  return { score, passed, status, headline, message };
}
