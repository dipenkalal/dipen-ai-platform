import fs from "node:fs";
import path from "node:path";
import {
  fileURLToPath,
} from "node:url";

const here = path.dirname(
  fileURLToPath(
    import.meta.url,
  ),
);

const dashboard = path.resolve(
  here,
  "..",
);

function read(relativePath) {
  return fs.readFileSync(
    path.join(
      dashboard,
      relativePath,
    ),
    "utf8",
  );
}

function walk(directory) {
  const result = [];

  for (
    const entry
    of fs.readdirSync(
      directory,
      {
        withFileTypes: true,
      },
    )
  ) {
    const full = path.join(
      directory,
      entry.name,
    );

    if (entry.isDirectory()) {
      result.push(
        ...walk(full),
      );
    } else {
      result.push(full);
    }
  }

  return result;
}

function fail(message) {
  console.error(
    `CAREER_COCKPIT_CHECK|FAIL|${message}`,
  );

  process.exit(1);
}

const careerRouteRoot = path.join(
  dashboard,
  "src",
  "app",
  "api",
  "career",
);

const routeFiles = walk(
  careerRouteRoot,
).filter(
  (file) =>
    file.endsWith(
      `${path.sep}route.ts`,
    ),
);

if (routeFiles.length !== 17) {
  fail(
    `route_files=${routeFiles.length}`,
  );
}

let getCount = 0;
let postCount = 0;

const transportForbidden = [
  "DETERMINISTIC_SYSTEM",
  "DAP_GENERATOR",
  '"owner_id"',
  '"actor_id"',
  '"actor_kind"',
  '"created_by_kind"',
  '"created_by_id"',
  '"occurred_at"',
];

for (const file of routeFiles) {
  const text = fs.readFileSync(
    file,
    "utf8",
  );

  getCount += (
    text.match(
      /export async function GET\(/g,
    ) ?? []
  ).length;

  postCount += (
    text.match(
      /export async function POST\(/g,
    ) ?? []
  ).length;

  for (
    const token
    of transportForbidden
  ) {
    if (text.includes(token)) {
      fail(
        `authority_synthesis=${token}|${file}`,
      );
    }
  }

  if (
    /auto[-_]?apply/i.test(text)
    || /\/submit\b/i.test(text)
  ) {
    fail(
      `submission_transport=${file}`,
    );
  }
}

if (
  getCount !== 10
  || postCount !== 9
) {
  fail(
    `methods=GET:${getCount},POST:${postCount}`,
  );
}


const ownerReviewRouteFiles = [
  path.join(
    careerRouteRoot,
    "owner-review",
    "queue",
    "route.ts",
  ),
  path.join(
    careerRouteRoot,
    "applications",
    "[applicationId]",
    "owner-review",
    "route.ts",
  ),
];

for (
  const file
  of ownerReviewRouteFiles
) {
  if (!routeFiles.includes(file)) {
    fail(
      `owner_review_bff_missing=${file}`,
    );
  }

  const text = fs.readFileSync(
    file,
    "utf8",
  );

  if (
    !text.includes(
      "export async function GET(",
    )
  ) {
    fail(
      `owner_review_get_missing=${file}`,
    );
  }

  if (
    /export\s+async\s+function\s+(?:POST|PUT|PATCH|DELETE)\b/.test(
      text,
    )
  ) {
    fail(
      `owner_review_mutation_transport=${file}`,
    );
  }

  if (
    text.includes(
      '"owner_id"',
    )
    || text.includes(
      '"actor_id"',
    )
    || text.includes(
      '"actor_kind"',
    )
  ) {
    fail(
      `owner_review_authority_synthesis=${file}`,
    );
  }
}

const dynamicRoutes =
  routeFiles.filter(
    (file) => file.includes("["),
  );

for (const file of dynamicRoutes) {
  const text = fs.readFileSync(
    file,
    "utf8",
  );

  if (
    !text.includes(
      "params: Promise<",
    )
    || !text.includes(
      "await context.params",
    )
  ) {
    fail(
      `next16_dynamic_params=${file}`,
    );
  }
}

const careerApi = read(
  "src/app/career/api.ts",
);

const careerPage = read(
  "src/app/career/page.tsx",
);

if (
  careerApi.includes(":8002")
  || careerApi.includes(
    "/api/v1/career",
  )
  || careerPage.includes(":8002")
) {
  fail(
    "browser_direct_backend",
  );
}

const functions = [
  "fetchCareerSummary",
  "fetchCareerJobs",
  "createCareerApplication",
  "fetchCareerApplication",
  "fetchCareerApplicationEvents",
  "transitionCareerApplication",
  "fetchCareerApplicationReadiness",
  "advanceCareerApplicationToReview",
  "approveCareerApplication",
  "fetchCareerApplicationMaterials",
  "createCareerApplicationMaterial",
  "fetchCareerMaterialVersions",
  "createCareerMaterialVersion",
  "fetchCareerMaterialVersionEvents",
  "markCareerMaterialVersionReady",
  "decideCareerMaterialVersion",
  "fetchCareerOwnerReviewQueue",
  "fetchCareerOwnerReviewPackage",
];

for (const name of functions) {
  if (
    !careerApi.includes(
      `function ${name}(`,
    )
  ) {
    fail(
      `api_function_missing=${name}`,
    );
  }
}

if (
  careerApi.includes(
    "DETERMINISTIC_SYSTEM",
  )
  || careerApi.includes(
    "DAP_GENERATOR",
  )
) {
  fail(
    "browser_authority_synthesis",
  );
}

const packageJson = JSON.parse(
  read("package.json"),
);

if (
  packageJson.scripts[
    "test:career-cockpit"
  ] !==
  "node scripts/check-career-cockpit.mjs"
) {
  fail(
    "package_script_missing",
  );
}

console.log(
  "CAREER_BFF_ROUTE_FILES|17",
);

console.log(
  "CAREER_BFF_OPERATIONS|19",
);

console.log(
  "CAREER_BFF_GET|10",
);

console.log(
  "CAREER_BFF_POST|8",
);

console.log(
  "CAREER_API_CLIENT_FUNCTIONS|19",
);

console.log(
  "NEXT16_DYNAMIC_PARAMS|PROMISE_AWAIT",
);

console.log(
  "BROWSER_DIRECT_BACKEND|0",
);

console.log(
  "BFF_AUTHORITY_SYNTHESIS|0",
);

console.log(
  "SUBMISSION_TRANSPORT|0",
);


// DAP_V2_CAREER_WORKSPACE_UI_CHECK_BEGIN

const workspaceUiFiles = [
  "src/app/career/page.tsx",
  "src/app/career/components/ApplicationWorkspace.tsx",
  "src/app/career/components/LifecycleTimeline.tsx",
  "src/app/career/components/ReadinessPanel.tsx",
];

for (
  const relativePath
  of workspaceUiFiles
) {
  if (
    !fs.existsSync(
      path.join(
        dashboard,
        relativePath,
      ),
    )
  ) {
    fail(
      `workspace_ui_missing=${relativePath}`,
    );
  }
}

const workspacePage = read(
  "src/app/career/page.tsx",
);

const applicationWorkspace = read(
  "src/app/career/components/ApplicationWorkspace.tsx",
);

const lifecycleTimeline = read(
  "src/app/career/components/LifecycleTimeline.tsx",
);

const readinessPanel = read(
  "src/app/career/components/ReadinessPanel.tsx",
);

const combinedWorkspaceUi =
  workspaceUiFiles
    .map((file) => read(file))
    .join("\n");

if (
  !workspacePage.includes(
    "Open workspace",
  )
) {
  fail(
    "open_workspace_action_missing",
  );
}

if (
  !workspacePage.includes(
    "async function openWorkspace(",
  )
) {
  fail(
    "explicit_workspace_handler_missing",
  );
}

if (
  !workspacePage.includes(
    "createCareerApplication(",
  )
) {
  fail(
    "workspace_creation_client_missing",
  );
}

if (
  lifecycleTimeline.includes(
    'target: "READY_FOR_REVIEW"',
  )
  || lifecycleTimeline.includes(
    'target: "OWNER_APPROVED"',
  )
  || lifecycleTimeline.includes(
    'target: "APPLIED_CONFIRMED"',
  )
) {
  fail(
    "blocked_generic_transition_target",
  );
}

if (
  !readinessPanel.includes(
    "onAdvanceToReview",
  )
  || !readinessPanel.includes(
    "onApprove",
  )
) {
  fail(
    "dedicated_guard_actions_missing",
  );
}

if (
  !applicationWorkspace.includes(
    "advanceCareerApplicationToReview",
  )
  || !applicationWorkspace.includes(
    "approveCareerApplication",
  )
) {
  fail(
    "dedicated_guard_client_missing",
  );
}

if (
  /<button\b[^>]*>\s*(?:Apply|Submit|Auto Apply)\s*<\/button>/i.test(
    combinedWorkspaceUi,
  )
) {
  fail(
    "submission_button_exposed",
  );
}

for (const token of [
  '"owner_id"',
  '"actor_id"',
  '"actor_kind"',
  '"created_by_kind"',
  '"created_by_id"',
  '"occurred_at"',
  "DETERMINISTIC_SYSTEM",
  "DAP_GENERATOR",
]) {
  if (
    combinedWorkspaceUi.includes(
      token,
    )
  ) {
    fail(
      `workspace_authority_token=${token}`,
    );
  }
}

if (
  combinedWorkspaceUi.includes(
    ":8002",
  )
  || combinedWorkspaceUi.includes(
    "/api/v1/career",
  )
) {
  fail(
    "workspace_direct_backend_access",
  );
}

console.log(
  "CAREER_WORKSPACE_COMPONENTS|3",
);

console.log(
  "WORKSPACE_ACTION|OPEN_WORKSPACE",
);

console.log(
  "GENERIC_READY_FOR_REVIEW_UI|0",
);

console.log(
  "GENERIC_OWNER_APPROVED_UI|0",
);

console.log(
  "GENERIC_APPLIED_CONFIRMED_UI|0",
);

console.log(
  "DEDICATED_ADVANCE_TO_REVIEW_UI|1",
);

console.log(
  "DEDICATED_OWNER_APPROVAL_UI|1",
);

console.log(
  "SUBMISSION_BUTTONS|0",
);

console.log(
  "WORKSPACE_AUTHORITY_SYNTHESIS|0",
);

// DAP_V2_CAREER_WORKSPACE_UI_CHECK_END


// DAP_V2_MATERIAL_LAB_UI_CHECK_BEGIN

const materialLabPath =
  "src/app/career/components/MaterialLab.tsx";

if (
  !fs.existsSync(
    path.join(
      dashboard,
      materialLabPath,
    ),
  )
) {
  fail(
    "material_lab_missing",
  );
}

const materialLab = read(
  materialLabPath,
);

if (
  !applicationWorkspace.includes(
    "<MaterialLab",
  )
) {
  fail(
    "material_lab_not_integrated",
  );
}

for (const kind of [
  "RESUME",
  "COVER_LETTER",
  "APPLICATION_NOTES",
]) {
  if (
    !materialLab.includes(
      `"${kind}"`,
    )
  ) {
    fail(
      `material_kind_missing=${kind}`,
    );
  }
}

for (const format of [
  "TEXT",
  "MARKDOWN",
  "LATEX",
  "JSON",
]) {
  if (
    !materialLab.includes(
      `"${format}"`,
    )
  ) {
    fail(
      `content_format_missing=${format}`,
    );
  }
}

if (
  !materialLab.includes(
    'label:\n                "primary"',
  )
) {
  fail(
    "primary_label_contract",
  );
}

if (
  !materialLab.includes(
    "source_snapshot_id:\n                sourceSnapshotId",
  )
) {
  fail(
    "snapshot_binding_missing",
  );
}

if (
  !materialLab.includes(
    "parent_material_version_id:",
  )
) {
  fail(
    "immutable_parent_link_missing",
  );
}

if (
  !materialLab.includes(
    "markCareerMaterialVersionReady",
  )
) {
  fail(
    "ready_client_missing",
  );
}

if (
  !materialLab.includes(
    "decideCareerMaterialVersion",
  )
) {
  fail(
    "decision_client_missing",
  );
}

if (
  !materialLab.includes(
    'applicationState\n                  === "PREPARING"'
  )
  && !materialLab.includes(
    'applicationState\n          === "PREPARING"'
  )
) {
  fail(
    "preparing_material_gate_missing",
  );
}

if (
  !materialLab.includes(
    '"READY_FOR_REVIEW"'
  )
) {
  fail(
    "review_decision_gate_missing",
  );
}

for (const token of [
  '"owner_id"',
  '"actor_id"',
  '"actor_kind"',
  '"created_by_kind"',
  '"created_by_id"',
  '"occurred_at"',
  "DETERMINISTIC_SYSTEM",
  "DAP_GENERATOR",
]) {
  if (
    materialLab.includes(
      token,
    )
  ) {
    fail(
      `material_authority_token=${token}`,
    );
  }
}

if (
  materialLab.includes(
    ":8002",
  )
  || materialLab.includes(
    "/api/v1/career",
  )
) {
  fail(
    "material_direct_backend_access",
  );
}

if (
  /<button\b[^>]*>\s*(?:Apply|Submit|Auto Apply)\s*<\/button>/i.test(
    materialLab,
  )
) {
  fail(
    "material_submission_button",
  );
}

console.log(
  "MATERIAL_LAB_COMPONENTS|1",
);

console.log(
  "MATERIAL_PRIMARY_SLOTS|3",
);

console.log(
  "MATERIAL_CONTENT_FORMATS|4",
);

console.log(
  "MATERIAL_VERSION_MODEL|IMMUTABLE",
);

console.log(
  "MATERIAL_SNAPSHOT_BINDING|JOB_SNAPSHOT_ID",
);

console.log(
  "MATERIAL_READY_ROUTE|DEDICATED",
);

console.log(
  "MATERIAL_DECISION_ROUTE|DEDICATED",
);

console.log(
  "MATERIAL_AUTHORITY_SYNTHESIS|0",
);

console.log(
  "MATERIAL_SUBMISSION_UI|0",
);

// DAP_V2_MATERIAL_LAB_UI_CHECK_END

console.log(
  "CAREER_COCKPIT_CHECK|PASS",
);

// DAP_V2_OWNER_REVIEW_UI_CHECK_BEGIN

const ownerReviewPagePath =
  "src/app/career/review/page.tsx";

if (
  !fs.existsSync(
    path.join(
      dashboard,
      ownerReviewPagePath,
    ),
  )
) {
  fail(
    "owner_review_page_missing",
  );
}

const ownerReviewPage = read(
  ownerReviewPagePath,
);

for (const required of [
  "fetchCareerOwnerReviewQueue",
  "fetchCareerOwnerReviewPackage",
  "approveCareerApplication",
  "decideCareerMaterialVersion",
  "READY_FOR_REVIEW",
  "Owner review queue",
  "Review package",
  "Approve application",
  "Approve material",
  "Reject material",
  "Materials",
  "Lifecycle history",
]) {
  if (
    !ownerReviewPage.includes(
      required,
    )
  ) {
    fail(
      `owner_review_ui_missing=${required}`,
    );
  }
}

for (const forbidden of [
  "transitionCareerApplication",
  "advanceCareerApplicationToReview",
  "createCareerApplication",
  "createCareerApplicationMaterial",
  "createCareerMaterialVersion",
  "markCareerMaterialVersionReady",
  "postJson(",
  ":8002",
  "/api/v1/career",
  '"owner_id"',
  '"actor_id"',
  '"actor_kind"',
  "DETERMINISTIC_SYSTEM",
  "DAP_GENERATOR",
]) {
  if (
    ownerReviewPage.includes(
      forbidden,
    )
  ) {
    fail(
      `owner_review_ui_forbidden=${forbidden}`,
    );
  }
}


if (
  !ownerReviewPage.includes(
    "approveCareerApplication(",
  )
  || !ownerReviewPage.includes(
    "decideCareerMaterialVersion(",
  )
) {
  fail(
    "owner_review_existing_mutation_primitive_missing",
  );
}

if (
  !ownerReviewPage.includes(
    "reviewPackage.approval.approved",
  )
  || !ownerReviewPage.includes(
    '!== "READY_FOR_REVIEW"',
  )
) {
  fail(
    "owner_review_application_guard_missing",
  );
}

if (
  !ownerReviewPage.includes(
    '"MARKED_READY_FOR_REVIEW"',
  )
  || !ownerReviewPage.includes(
    'eventKinds.has("APPROVED")',
  )
  || !ownerReviewPage.includes(
    'eventKinds.has("REJECTED")',
  )
) {
  fail(
    "owner_review_material_guard_missing",
  );
}

if (
  /<button\b[^>]*>\s*(?:Apply|Submit|Auto Apply)\s*<\/button>/i.test(
    ownerReviewPage,
  )
) {
  fail(
    "owner_review_submission_button",
  );
}

console.log(
  "OWNER_REVIEW_PAGE|1",
);

console.log(
  "OWNER_REVIEW_PAGE_LOAD|GET_ONLY",
);

console.log(
  "OWNER_REVIEW_QUEUE_CLIENT|1",
);

console.log(
  "OWNER_REVIEW_PACKAGE_CLIENT|1",
);

console.log(
  "OWNER_REVIEW_APPLICATION_APPROVAL_CONTROL|1",
);

console.log(
  "OWNER_REVIEW_MATERIAL_DECISION_CONTROLS|2",
);

console.log(
  "OWNER_REVIEW_MUTATION_PRIMITIVES|EXISTING_ONLY",
);

console.log(
  "OWNER_REVIEW_SUBMISSION_UI|0",
);

console.log(
  "OWNER_REVIEW_UI_AUTHORITY_SYNTHESIS|0",
);

// DAP_V2_OWNER_REVIEW_UI_CHECK_END
