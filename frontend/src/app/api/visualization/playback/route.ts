import {
  NextRequest,
  NextResponse,
} from "next/server";


const API_URL =
  process.env.ORBITAL_API_URL ??
  "http://127.0.0.1:8008";


export async function GET(
  request: NextRequest,
) {
  const incoming =
    request.nextUrl.searchParams;

  const upstream =
    new URL(
      "/visualization/playback",
      API_URL,
    );


  for (
    const key
    of [
      "start",
      "end",
      "step_seconds",
    ]
  ) {
    const value =
      incoming.get(
        key,
      );

    if (value !== null) {
      upstream.searchParams.set(
        key,
        value,
      );
    }
  }


  try {
    const response =
      await fetch(
        upstream,
        {
          cache: "no-store",
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
          "OrbitalAI backend unavailable",
      },
      {
        status: 502,
      },
    );
  }
}
