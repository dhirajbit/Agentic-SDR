CREATE TABLE "actions" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"source_key" text NOT NULL,
	"channel" text NOT NULL,
	"company" text,
	"recipient" text,
	"framework" text,
	"subject" text,
	"body" text,
	"message_id" text,
	"chat_id" text,
	"status" text,
	"dry_run" boolean,
	"events" jsonb DEFAULT '{}'::jsonb,
	"occurred_at" timestamp with time zone NOT NULL
);
--> statement-breakpoint
CREATE TABLE "commands" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"type" text NOT NULL,
	"args" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'pending' NOT NULL,
	"requested_by" text,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	"claimed_at" timestamp with time zone,
	"finished_at" timestamp with time zone,
	"result" jsonb
);
--> statement-breakpoint
CREATE TABLE "credit_snapshots" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"at" timestamp with time zone NOT NULL,
	"label" text,
	"lead_credit_left" integer,
	"direct_dial_credit_left" integer,
	"export_credit_left" integer,
	"cycle_start" date,
	"cycle_end" date
);
--> statement-breakpoint
CREATE TABLE "cycle_runs" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"kind" text NOT NULL,
	"status" text DEFAULT 'pending' NOT NULL,
	"trigger" text,
	"command_id" uuid,
	"started_at" timestamp with time zone,
	"finished_at" timestamp with time zone,
	"summary" jsonb,
	"log" text
);
--> statement-breakpoint
CREATE TABLE "integrations" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"provider" text NOT NULL,
	"config" jsonb DEFAULT '{}'::jsonb,
	"secrets_ciphertext" jsonb DEFAULT '{}'::jsonb,
	"status" text DEFAULT 'unconfigured' NOT NULL,
	"status_detail" jsonb DEFAULT '{}'::jsonb,
	"last_checked_at" timestamp with time zone,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "leads" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"tenant_id" uuid NOT NULL,
	"external_id" text NOT NULL,
	"company" text,
	"email" text,
	"mobile" text,
	"status" text NOT NULL,
	"payload" jsonb,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL
);
--> statement-breakpoint
CREATE TABLE "settings" (
	"tenant_id" uuid PRIMARY KEY NOT NULL,
	"live_send" boolean DEFAULT false NOT NULL,
	"auto_loop" boolean DEFAULT false NOT NULL,
	"updated_at" timestamp with time zone DEFAULT now() NOT NULL,
	"updated_by" text
);
--> statement-breakpoint
CREATE TABLE "tenants" (
	"id" uuid PRIMARY KEY DEFAULT gen_random_uuid() NOT NULL,
	"clerk_org_id" text NOT NULL,
	"slug" text NOT NULL,
	"name" text NOT NULL,
	"driver" text DEFAULT 'sdr_cycle' NOT NULL,
	"worker_public_key" text,
	"worker_last_seen_at" timestamp with time zone,
	"created_at" timestamp with time zone DEFAULT now() NOT NULL,
	CONSTRAINT "tenants_clerk_org_id_unique" UNIQUE("clerk_org_id"),
	CONSTRAINT "tenants_slug_unique" UNIQUE("slug")
);
--> statement-breakpoint
ALTER TABLE "actions" ADD CONSTRAINT "actions_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "commands" ADD CONSTRAINT "commands_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "credit_snapshots" ADD CONSTRAINT "credit_snapshots_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "cycle_runs" ADD CONSTRAINT "cycle_runs_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "integrations" ADD CONSTRAINT "integrations_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "leads" ADD CONSTRAINT "leads_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
ALTER TABLE "settings" ADD CONSTRAINT "settings_tenant_id_tenants_id_fk" FOREIGN KEY ("tenant_id") REFERENCES "public"."tenants"("id") ON DELETE cascade ON UPDATE no action;--> statement-breakpoint
CREATE UNIQUE INDEX "actions_tenant_sourcekey_uq" ON "actions" USING btree ("tenant_id","source_key");--> statement-breakpoint
CREATE INDEX "actions_tenant_occurred_idx" ON "actions" USING btree ("tenant_id","occurred_at" DESC NULLS LAST);--> statement-breakpoint
CREATE INDEX "actions_tenant_channel_occurred_idx" ON "actions" USING btree ("tenant_id","channel","occurred_at" DESC NULLS LAST);--> statement-breakpoint
CREATE INDEX "commands_tenant_status_created_idx" ON "commands" USING btree ("tenant_id","status","created_at");--> statement-breakpoint
CREATE INDEX "commands_pending_idx" ON "commands" USING btree ("status") WHERE "commands"."status" = 'pending';--> statement-breakpoint
CREATE INDEX "credit_snapshots_tenant_at_idx" ON "credit_snapshots" USING btree ("tenant_id","at" DESC NULLS LAST);--> statement-breakpoint
CREATE INDEX "cycle_runs_tenant_started_idx" ON "cycle_runs" USING btree ("tenant_id","started_at" DESC NULLS LAST);--> statement-breakpoint
CREATE UNIQUE INDEX "integrations_tenant_provider_uq" ON "integrations" USING btree ("tenant_id","provider");--> statement-breakpoint
CREATE UNIQUE INDEX "leads_tenant_extid_status_uq" ON "leads" USING btree ("tenant_id","external_id","status");--> statement-breakpoint
CREATE INDEX "leads_tenant_status_idx" ON "leads" USING btree ("tenant_id","status");