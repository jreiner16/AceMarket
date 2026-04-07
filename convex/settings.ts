import { v } from "convex/values";
import { mutation, query } from "./_generated/server";

export const getSettings = query({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    const row = await ctx.db
      .query("settings")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .unique();
    return row ? row.settingsJson : null;
  },
});

export const saveSettings = mutation({
  args: { userId: v.string(), settingsJson: v.string() },
  handler: async (ctx, { userId, settingsJson }) => {
    const existing = await ctx.db
      .query("settings")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .unique();
    if (existing) {
      await ctx.db.patch(existing._id, { settingsJson });
    } else {
      await ctx.db.insert("settings", { userId, settingsJson });
    }
  },
});
