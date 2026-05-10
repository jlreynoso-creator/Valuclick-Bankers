import type { Context } from "@netlify/functions";
import { eq } from "drizzle-orm";
import db from "../../db/index.js";
import { users, searchLogs } from "../../db/schema.js";
import {
  getUserFromRequest,
  jsonResponse,
  errorResponse,
} from "./utils/auth.mjs";

export default async function handler(request: Request, _context: Context) {
  if (request.method !== "POST") {
    return errorResponse("Method not allowed", 405);
  }

  const tokenData = await getUserFromRequest(request);
  if (!tokenData) {
    return jsonResponse(
      {
        results: [],
        remaining_searches: 0,
        blocked: true,
        message:
          "Crea una cuenta para buscar. Obtén 2 búsquedas gratuitas.",
      },
      200,
    );
  }

  let body: { query?: string; portales?: string[] };
  try {
    body = await request.json();
  } catch {
    return errorResponse("Invalid JSON body");
  }

  const { query, portales } = body;
  if (!query) {
    return errorResponse("Query es requerido");
  }

  const [user] = await db
    .select()
    .from(users)
    .where(eq(users.id, tokenData.userId))
    .limit(1);

  if (!user) {
    return errorResponse("Usuario no encontrado", 404);
  }

  const isFree = user.subscriptionPlan === "free";
  const isSubscriptionActive =
    !isFree &&
    user.subscriptionExpires !== null &&
    new Date() < new Date(user.subscriptionExpires);
  const canSearch = isFree ? user.searchCount < 2 : isSubscriptionActive;

  if (!canSearch) {
    return jsonResponse({
      results: [],
      remaining_searches: 0,
      blocked: true,
      message:
        "Límite de búsquedas alcanzado. Suscríbete para acceso ilimitado.",
    });
  }

  const results = [
    {
      id: 1,
      title: `Resultado para: ${query}`,
      price: "$500,000",
      location: "Boca del Río, Veracruz",
      portal: "inmuebles24",
    },
  ];

  await db.insert(searchLogs).values({
    userId: user.id,
    query,
    portalesSearched: JSON.stringify(portales || []),
    resultCount: results.length,
  });

  await db
    .update(users)
    .set({
      searchCount: user.searchCount + 1,
      lastSearchDate: new Date(),
      updatedAt: new Date(),
    })
    .where(eq(users.id, user.id));

  const remaining = isFree ? Math.max(0, 2 - (user.searchCount + 1)) : 999;

  return jsonResponse({
    results,
    remaining_searches: remaining,
    blocked: false,
    message: "Búsqueda exitosa",
  });
}

export const config = {
  path: "/api/search",
  method: "POST",
};
