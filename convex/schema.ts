import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";

export default defineSchema({
  settings: defineTable({
    userId: v.string(),
    settingsJson: v.string(),
  }).index("by_user", ["userId"]),

  portfolios: defineTable({
    userId: v.string(),
    cash: v.number(),
    positionsJson: v.string(),
    tradeLogJson: v.string(),
    equityCurveJson: v.string(),
    realizedJson: v.string(),
  }).index("by_user", ["userId"]),

  strategies: defineTable({
    userId: v.string(),
    name: v.string(),
    code: v.string(),
    createdAt: v.string(),
  })
    .index("by_user", ["userId"])
    .index("by_user_name", ["userId", "name"]),

  runs: defineTable({
    userId: v.string(),
    strategyId: v.string(),
    strategyName: v.string(),
    symbolsJson: v.string(),
    startDate: v.string(),
    endDate: v.string(),
    resultsJson: v.string(),
    portfolioJson: v.string(),
    metricsJson: v.string(),
    createdAt: v.string(),
  }).index("by_user", ["userId"]),
});
