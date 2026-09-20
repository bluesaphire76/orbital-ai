import {
  NextResponse,
} from "next/server";


const API_URL =
  process.env.ORBITAL_API_URL ??
  "http://127.0.0.1:8008";


export async function GET() {
  const upstream =
    new URL(
      "/catalog/sync-status",
      API_URL,
    );

  try {
    const response =
      await fetch(
        upstream,
        {
          cache:
            "no-store",
        },
      );

    const body =
      await response.text();

    return new NextResponse(
      body,
      {
        status:
          response.status,

        headers: {
          "content-type":
            response.headers.get(
              "content-type",
            )
            ?? "application/json",
        },
      },
    );

  } catch {
    return NextResponse.json(
      {
        detail:
          "Catalog synchronization status is temporarily unavailable.",
      },
      {
        status: 502,
      },
    );
  }
}
