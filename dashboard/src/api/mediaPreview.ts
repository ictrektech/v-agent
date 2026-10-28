import { requestBlob } from "./request";
import { isNotFoundApiError } from "../utils/apiError";

/** Old media links may reference a delivered file outside the expert workspace. */
export async function requestMediaBlob(
  apiPath: string,
  options?: RequestInit,
): Promise<Blob> {
  try {
    return await requestBlob(apiPath, options);
  } catch (error) {
    const match = apiPath.match(
      /^\/(?:api\/)?agents\/([^/]+)\/media\/preview\?/,
    );
    const source = new URLSearchParams(apiPath.split("?")[1]).get("source");
    if (
      !isNotFoundApiError(error) ||
      !match ||
      !source ||
      !/^(?:file:\/\/|\/|[A-Za-z]:[\\/])/.test(source)
    )
      throw error;
    // Reuse the existing download endpoint and its owner/path permission checks.
    return requestBlob(
      `/agents/${match[1]}/workspace/download?${new URLSearchParams({
        path: source,
      })}`,
      options,
    );
  }
}
