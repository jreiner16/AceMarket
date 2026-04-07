import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const getStrategies = query({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    const rows = await ctx.db
      .query("strategies")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .collect();
    return rows.map((r) => ({
      id: r._id,
      name: r.name,
      code: r.code,
      createdAt: r.createdAt,
    }));
  },
});

export const getStrategy = query({
  args: { userId: v.string(), strategyId: v.id("strategies") },
  handler: async (ctx, { userId, strategyId }) => {
    const row = await ctx.db.get(strategyId);
    if (!row || row.userId !== userId) return null;
    return { id: row._id, name: row.name, code: row.code };
  },
});

export const createStrategy = mutation({
  args: { userId: v.string(), name: v.string(), code: v.string() },
  handler: async (ctx, { userId, name, code }) => {
    const createdAt = new Date().toISOString();
    const id = await ctx.db.insert("strategies", { userId, name, code, createdAt });
    return { id, name, code };
  },
});

export const updateStrategy = mutation({
  args: {
    userId: v.string(),
    strategyId: v.id("strategies"),
    name: v.union(v.string(), v.null()),
    code: v.union(v.string(), v.null()),
  },
  handler: async (ctx, { userId, strategyId, name, code }) => {
    const row = await ctx.db.get(strategyId);
    if (!row || row.userId !== userId) return null;
    const newName = name !== null ? name : row.name;
    const newCode = code !== null ? code : row.code;
    await ctx.db.patch(strategyId, { name: newName, code: newCode });
    return { id: strategyId, name: newName, code: newCode };
  },
});

export const deleteStrategy = mutation({
  args: { userId: v.string(), strategyId: v.id("strategies") },
  handler: async (ctx, { userId, strategyId }) => {
    const row = await ctx.db.get(strategyId);
    if (!row || row.userId !== userId) return false;
    await ctx.db.delete(strategyId);
    return true;
  },
});
