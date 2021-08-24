/** @odoo-module **/

    import MockServer from 'web.MockServer';

    MockServer.include({
        //--------------------------------------------------------------------------
        // Private
        //--------------------------------------------------------------------------

        /**
         * @override
         * @private
         */
        async _performRpc(route, args) {
            if (args.model === 'crm.lead' && args.method === 'get_rainbowman_message') {
                let message = false;
                const records = this.data['crm.lead'].records;
                const record = records.find(r => r.id === args.args[0][0]);
                const won_stage = this.data['crm.stage'].records.find(s => s.is_won);
                if (record.stage_id === won_stage.id && record.user_id && record.team_id && record.planned_revenue > 0) {
                    const now = moment();
                    let query_result = {};
                    // Total won
                    query_result['total_won'] = records.filter(r => r.stage_id === won_stage.id && r.user_id === record.user_id).length;
                    // Max team 30 days
                    const recordsTeam30 = records.filter(r => r.stage_id === won_stage.id && r.team_id === record.team_id && (!r.date_closed || moment.duration(now.diff(moment(r.date_closed))).days() <= 30));
                    query_result['max_team_30'] = Math.max(...recordsTeam30.map(r => r.planned_revenue));
                    // Max team 7 days
                    const recordsTeam7 = records.filter(r => r.stage_id === won_stage.id && r.team_id === record.team_id && (!r.date_closed || moment.duration(now.diff(moment(r.date_closed))).days() <= 7));
                    query_result['max_team_7'] = Math.max(...recordsTeam7.map(r => r.planned_revenue));
                    // Max User 30 days
                    const recordsUser30 = records.filter(r => r.stage_id === won_stage.id && r.user_id === record.user_id && (!r.date_closed || moment.duration(now.diff(moment(r.date_closed))).days() <= 30));
                    query_result['max_user_30'] = Math.max(...recordsUser30.map(r => r.planned_revenue));
                    // Max User 7 days
                    const recordsUser7 = records.filter(r => r.stage_id === won_stage.id && r.user_id === record.user_id && (!r.date_closed || moment.duration(now.diff(moment(r.date_closed))).days() <= 7));
                    query_result['max_user_7'] = Math.max(...recordsUser7.map(r => r.planned_revenue));

                    if (query_result.total_won === 1) {
                        message = "Go, go, go! Congrats for your first deal.";
                    } else if (query_result.max_team_30 === record.planned_revenue) {
                        message = "Boom! Team record for the past 30 days.";
                    } else if (query_result.max_team_7 === record.planned_revenue) {
                        message = "Yeah! Deal of the last 7 days for the team.";
                    } else if (query_result.max_user_30 === record.planned_revenue) {
                        message = "You just beat your personal record for the past 30 days.";
                    } else if (query_result.max_user_7 === record.planned_revenue) {
                        message = "You just beat your personal record for the past 7 days.";
                    }
                }
                return message;
            }
            return this._super(...arguments);
        },
    });
