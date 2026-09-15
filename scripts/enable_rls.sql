-- ============================================================================
-- Farm Control - Row Level Security PostgreSQL (paragraphe 7.2)
-- ============================================================================
-- Couche 2 de securite multitenant, en complement du filtrage applicatif
-- (couche 1, voir app/models/__init__.py). Meme si une requete applicative
-- oublie le filtre tenant_id par erreur, PostgreSQL refuse de retourner les
-- lignes d'un autre tenant.
--
-- A executer APRES `flask db upgrade` (les tables doivent exister), avec un
-- role superuser (ex. postgres). Le role applicatif utilise par Flask
-- (ex. farmcontrol) ne doit PAS avoir l'attribut BYPASSRLS, et ne doit pas
-- etre proprietaire des tables si l'on veut que FORCE ROW LEVEL SECURITY
-- s'applique meme au proprietaire.
--
-- Variables de session utilisees par l'application (voir app/utils/rls.py) :
--   app.current_tenant   -> id du tenant courant (entier, '-1' si aucun)
--   app.is_superadmin    -> 'true' pour un super administrateur (bypass)
-- ============================================================================

DO $$
DECLARE
    t text;
    tenant_scoped_tables text[] := ARRAY[
        'users',
        'password_reset_tokens',
        'audit_log',
        'farms',
        'poultry_batches',
        'poultry_batch_days',
        'poultry_stock_items',
        'poultry_feed_records',
        'poultry_water_records',
        'poultry_mortality_records',
        'poultry_wood_records',
        'poultry_medication_records',
        'poultry_observations',
        'poultry_weight_records',
        'poultry_batch_finance',
        'alerts',
        'poultry_sanitary_program_items',
        'poultry_daily_reports',
        'poultry_growth_references',
        'poultry_growth_reference_points',
        'billing_subscriptions',
        'billing_payment_transactions',
        'messages',
        'poultry_sanitary_program_template_items',
        'poultry_suppliers',
        'poultry_sales',
        'email_verification_tokens'
    ];
BEGIN
    FOREACH t IN ARRAY tenant_scoped_tables LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', t);

        EXECUTE format('DROP POLICY IF EXISTS tenant_isolation_policy ON %I;', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation_policy ON %I
                USING (
                    tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''')::int
                    OR current_setting(''app.is_superadmin'', true) = ''true''
                )
                WITH CHECK (
                    tenant_id = NULLIF(current_setting(''app.current_tenant'', true), '''')::int
                    OR current_setting(''app.is_superadmin'', true) = ''true''
                );',
            t
        );
    END LOOP;
END $$;

-- La table `tenants` (annuaire des clients de la plateforme) n'est pas
-- filtree par tenant_id (elle EST le tenant). Seul le role applicatif normal
-- y accede en lecture seule via les jointures necessaires a l'authentification ;
-- la gestion (creation/desactivation de clients) passe toujours par le role
-- super_admin cote application (app.utils.tenant.tenant_bypass), qui positionne
-- app.is_superadmin = 'true'.
--
-- La table `billing_plans` (catalogue des formules tarifaires) n'est pas non
-- plus filtree par tenant : c'est un referentiel commun a tous les clients.
