// The Den: scoring and locks. Pure functions, no dependencies, no DOM.
// Mirrors mac/den.py exactly (same formulas, same order of operations, same half-up rounding).
// tests/test_den.py runs these against the Python and against the numbers below; change both together.
//
//   import * as Den from "/static/den.js";
//
// Known cases (also hard-coded in tests/test_den.py):
//   fantasyPoints({pts:8, reb:6, ast:5, blk:2, stl:1})            === 28.7
//   fantasyPoints([20, 7, 3, 0, 1])                                === 34.9
//   defensePoints({blk:4, stl:8, pa:46, ofgm:17, ofga:55})         === 33.5
//   defensePoints({blk:1, stl:4, pa:67, ofgm:24, ofga:53})         === 8.9
//   shootingPct({fgm:22, ftm:15, fga:59, fta:19})                  === 0.4744
//   pickWorth(0.504, "home") === 50,  pickWorth(0.504, "away") === 50
//   pickWorth(0.935, "home") === 6,   pickWorth(0.935, "away") === 94   (float: 100*(1-0.935) is 6.4999...)
//   brickWall(["hit","hit","stand","hit","miss","hit"])          -> {wall:1, best:3}
//
// Results files: site/den/results-YYYY-MM-DD.json (shape in mac/den.py's docstring).

const r = (x, places = 1) => { const k = 10 ** places; return Math.floor(x * k + 0.5) / k; };
export const round = r;

// Daily Five player: 1 per point, 1.2 per rebound, 1.5 per assist, 2 per block, 2 per steal.
// Takes {pts, reb, ast, blk, stl} or a results `stat` row [pts, reb, ast, blk, stl, min].
export function fantasyPoints(s) {
  const [pts, reb, ast, blk, stl] = Array.isArray(s) ? s : [s.pts, s.reb, s.ast, s.blk, s.stl];
  return r(pts + 1.2 * reb + 1.5 * ast + 2 * blk + 2 * stl);
}

// Daily Five team D: 1 per block and steal, + 0.5 (75 - points allowed) + 0.5 (45 - opponent FG%).
export function defensePoints({ blk, stl, pa, ofgm, ofga }) {
  return ofga ? r(blk + stl + 0.5 * (75 - pa) + 0.5 * (45 - 100 * ofgm / ofga)) : r(blk + stl + 0.5 * (75 - pa));
}

// Bricksanity: (FGM + FTM) / (FGA + FTA), 4 decimals.
export function shootingPct({ fgm, ftm, fga, fta }) {
  const a = fga + fta;
  return a ? r((fgm + ftm) / a, 4) : null;
}

// Pick 4 points for a right pick: round(100 x (1 - win chance of the side picked)). null if no line.
export function pickWorth(winHome, side) {
  if (winHome == null) return null;
  const p = side === "home" ? winHome : 1 - winHome;
  return Math.floor(100 * (1 - p) + 0.5);
}

// A game locks at its tip. nowMs defaults to the visitor's clock (client side only: see the report).
export function isLocked(tipIso, nowMs = Date.now()) {
  return nowMs >= Date.parse(tipIso);
}

// pick = {game, side: "home"|"away"} -> "win" | "loss" | "void" (never went final) | "pending".
export function pickOutcome(pick, results) {
  if (!results) return "pending";
  const g = results.games.find(x => x.id === pick.game);
  if (!g) return results.complete ? "void" : "pending";
  if (g.winner_id == null) return "void";
  const sideId = pick.side === "home" ? g.home_id : g.away_id;
  return sideId === g.winner_id ? "win" : "loss";
}

// Pick 4 total: the first 4 picks; a right pick earns the side's worth (frozen at the last line before tip).
export function pick4Score(picks, results) {
  let total = 0;
  for (const p of picks.slice(0, 4)) {
    if (pickOutcome(p, results) === "win") {
      const g = results.games.find(x => x.id === p.game);
      total += (g.worth && g.worth[p.side]) || 0;
    }
  }
  return total;
}

// Daily Five total: up to 5 player ids + 1 defense team id. A player who didn't play scores 0.
export function dailyFiveScore(players, defense, results) {
  if (!results) return 0;
  let s = 0;
  for (const p of players.slice(0, 5)) s += results.players[String(p)] || 0;
  if (defense != null) s += results.defenses[String(defense)] || 0;
  return r(s);
}

// Bricksanity: hit if either guess ties the night's lowest shooting. null until the night is complete.
export function bricksanityHit(guesses, results) {
  if (!results || !results.complete) return null;
  const vals = Object.values(results.shooting);
  if (!vals.length) return null;
  const low = Math.min(...vals);
  return guesses.slice(0, 2).some(g => results.shooting[String(g)] === low);
}

// Brick by Brick, one day: "hit" (4 for 4), "miss" (any wrong pick), "pending", or "stand"
// (no picks, fewer than 4, or a voided game with no misses: the wall stays as it is).
export function brickDay(picks, results) {
  const outs = picks.slice(0, 4).map(p => pickOutcome(p, results));
  if (outs.includes("loss")) return "miss";
  if (outs.includes("pending")) return "pending";
  return outs.length === 4 && outs.every(o => o === "win") ? "hit" : "stand";
}

// Brick by Brick wall from brickDay outcomes in date order -> {wall, best}.
export function brickWall(days) {
  let wall = 0, best = 0;
  for (const d of days) {
    if (d === "hit") { wall += 1; best = Math.max(best, wall); }
    else if (d === "miss") wall = 0;
  }
  return { wall, best };
}
