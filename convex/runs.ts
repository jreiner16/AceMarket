import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const saveRun = mutation({
  args: {
    userId: v.string(),
    strategyId: v.string(),
    strategyName: v.string(),
    symbolsJson: v.string(),
    startDate: v.string(),
    endDate: v.string(),
    resultsJson: v.string(),
    portfolioJson: v.string(),
    metricsJson: v.string(),
  },
  handler: async (ctx, args) => {
    const createdAt = new Date().toISOString();
    const id = await ctx.db.insert("runs", { ...args, createdAt });
    return id;
  },
});

export const getRuns = query({
  args: { userId: v.string(), limit: v.number() },
  handler: async (ctx, { userId, limit }) => {
    const rows = await ctx.db
      .query("runs")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .order("desc")
      .take(limit);
    return rows.map((r) => ({
      id: r._id,
      createdAt: r.createdAt,
      strategyId: r.strategyId,
      strategyName: r.strategyName,
      symbolsJson: r.symbolsJson,
      startDate: r.startDate,
      endDate: r.endDate,
      metricsJson: r.metricsJson,
      portfolioJson: r.portfolioJson,
    }));
  },
});

export const getRun = query({
  args: { userId: v.string(), runId: v.id("runs") },
  handler: async (ctx, { userId, runId }) => {
    const row = await ctx.db.get(runId);
    if (!row || row.userId !== userId) return null;
    return {
      id: row._id,
      createdAt: row.createdAt,
      strategyId: row.strategyId,
      strategyName: row.strategyName,
      symbolsJson: row.symbolsJson,
      startDate: row.startDate,
      endDate: row.endDate,
      resultsJson: row.resultsJson,
      portfolioJson: row.portfolioJson,
      metricsJson: row.metricsJson,
    };
  },
});

export const clearRuns = mutation({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    const rows = await ctx.db
      .query("runs")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .collect();
    await Promise.all(rows.map((r) => ctx.db.delete(r._id)));
  },
});
