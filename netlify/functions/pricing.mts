import type { Context } from "@netlify/functions";
import { jsonResponse } from "./utils/auth.mjs";

export default async function handler(_request: Request, _context: Context) {
  return jsonResponse({
    plans: [
      {
        id: "agente",
        name: "Plan Agente",
        price: 150,
        currency: "MXN",
        period: "monthly",
        features: [
          "Búsquedas ilimitadas",
          "Acceso a todos los portales",
          "Análisis básico",
          "Soporte por email",
        ],
      },
      {
        id: "despacho",
        name: "Plan Despacho",
        price: 300,
        currency: "MXN",
        period: "monthly",
        features: [
          "Búsquedas ilimitadas",
          "Acceso a todos los portales",
          "Análisis avanzado",
          "Reportes PDF",
          "Soporte prioritario",
        ],
      },
      {
        id: "institucional",
        name: "Plan Institucional",
        price: 1000,
        currency: "MXN",
        period: "monthly",
        features: [
          "Búsquedas ilimitadas",
          "Acceso a todos los portales",
          "Análisis enterprise",
          "API custom",
          "Soporte 24/7",
        ],
      },
    ],
  });
}

export const config = {
  path: "/api/pricing",
};
