import DigestFetch from "digest-fetch";
import { parseStringPromise } from "xml2js";

const client = new DigestFetch("admn", "2008-nce");
const url =
  "http://10.8.1.101/ISAPI/System/Video/inputs/channels/1/counting/search";

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<CountingStatisticsDescription>
  <statisticType>all</statisticType>
  <reportType>daily</reportType>
  <timeSpanList>
    <timeSpan>
      <startTime>2025-06-03T00:00:00</startTime>
      <endTime>2025-06-03T23:59:59</endTime>
    </timeSpan>
  </timeSpanList>
  <regionID>1,2,3,4,5</regionID>
</CountingStatisticsDescription>`;

async function fetchPeopleCounting(attempt = 1) {
  try {
    const res = await client.fetch(url, {
      method: "POST",
      body: xml,
      headers: { "Content-Type": "application/xml" },
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);

    const rawXml = await res.text();
    const json = await parseStringPromise(rawXml, { explicitArray: false });
    console.log(JSON.stringify(json, null, 2));
  } catch (err) {
    console.error(`Attempt ${attempt}: ${err.message}`);
    if (attempt < 10) {
      await new Promise((r) => setTimeout(r, 1000)); // wait 1 sec
      await fetchPeopleCounting(attempt + 1);
    } else {
      console.error("❌ Failed after 10 attempts. Exiting.");
    }
  }
}

fetchPeopleCounting();
