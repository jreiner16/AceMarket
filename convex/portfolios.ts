import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const getPortfolio = query({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    const row = await ctx.db
      .query("portfolios")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .unique();
    if (!row) return null;
    return {
      cash: row.cash,
      positionsJson: row.positionsJson,
      tradeLogJson: row.tradeLogJson,
      equityCurveJson: row.equityCurveJson,
      realizedJson: row.realizedJson,
    };
  },
});

export const savePortfolio = mutation({
  args: {
    userId: v.string(),
    cash: v.number(),
    positionsJson: v.string(),
    tradeLogJson: v.string(),
    equityCurveJson: v.string(),
    realizedJson: v.string(),
  },
  handler: async (ctx, { userId, cash, positionsJson, tradeLogJson, equityCurveJson, realizedJson }) => {
    const existing = await ctx.db
      .query("portfolios")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .unique();
    if (existing) {
      await ctx.db.patch(existing._id, { cash, positionsJson, tradeLogJson, equityCurveJson, realizedJson });
    } else {
      await ctx.db.insert("portfolios", { userId, cash, positionsJson, tradeLogJson, equityCurveJson, realizedJson });
    }
  },
});
