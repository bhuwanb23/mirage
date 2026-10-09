// ============================================================
// Mirage — Neo4j schema (Phase 0)
// Run in: Neo4j Browser (https://console.neo4j.io → Query)
// Idempotent: safe to re-run.
// ============================================================

// --- Uniqueness constraints (also create indexes) -----------
CREATE CONSTRAINT phone_if_not_exists      IF NOT EXISTS FOR (n:Phone)      REQUIRE n.value     IS UNIQUE;
CREATE CONSTRAINT upi_if_not_exists        IF NOT EXISTS FOR (n:UPI)        REQUIRE n.value     IS UNIQUE;
CREATE CONSTRAINT url_if_not_exists        IF NOT EXISTS FOR (n:URL)        REQUIRE n.value     IS UNIQUE;
CREATE CONSTRAINT domain_if_not_exists     IF NOT EXISTS FOR (n:Domain)     REQUIRE n.name      IS UNIQUE;
CREATE CONSTRAINT email_if_not_exists      IF NOT EXISTS FOR (n:Email)      REQUIRE n.value     IS UNIQUE;
CREATE CONSTRAINT account_if_not_exists    IF NOT EXISTS FOR (n:BankAccount)REQUIRE n.value     IS UNIQUE;
CREATE CONSTRAINT report_if_not_exists     IF NOT EXISTS FOR (n:ScamReport) REQUIRE n.id        IS UNIQUE;
CREATE CONSTRAINT campaign_if_not_exists   IF NOT EXISTS FOR (n:Campaign)   REQUIRE n.id        IS UNIQUE;

// --- Full-text index for IOC search -------------------------
CREATE FULLTEXT INDEX ioc_search IF NOT EXISTS
  FOR (n:Phone|UPI|URL|Domain|Email|BankAccount) ON EACH [n.value, n.name];

// --- Node labels used by Phase 5 ----------------------------
// Phone, UPI, URL, Domain, Email, BankAccount, ScamReport, Campaign
// --- Relationship types used by Phase 5 ---------------------
// (ScamReport)-[:MENTIONS]->(Phone|UPI|URL|Domain|Email|BankAccount)
// (Phone)-[:PART_OF]->(Campaign)
// (Domain)-[:RESOLVES_TO]->(URL)
// (Campaign)-[:OPERATED_BY]->(Campaign)
