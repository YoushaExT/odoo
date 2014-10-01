openerp.pos_loyalty = function(instance){

    var module   = instance.point_of_sale;
    var round_pr = instance.web.round_precision
    var QWeb     = instance.web.qweb;

    var models = module.PosModel.prototype.models;
    for (var i = 0; i < models.length; i++) {
        var model = models[i];
        if (model.model === 'product.product') {
            model.fields.push('loyalty_points');
            model.fields.push('loyalty_override');
        } else if (model.model === 'res.partner') {
            model.fields.push('loyalty_points');
        } else if (model.model === 'pos.config') {
            // load loyalty after pos.config
            models.splice(i+1,0,{
                model: 'loyalty.program',
                condition: function(self){ return !!self.config.loyalty_id[0]; },
                fields: ['name','pp_currency','pp_product','pp_order','rounding'],
                domain: function(self){ return [['id','=',self.config.loyalty_id[0]]]; },
                loaded: function(self,loyalties){ self.loyalty = loyalties[0]; },
            },{
                model: 'loyalty.rule',
                condition: function(self){ return !!self.loyalty; },
                fields: ['name','type','product_id','category_id','override','pp_product','pp_currency'],
                domain: function(self){ return [['loyalty_program_id','=',self.loyalty.id]]; },
                loaded: function(self,rules){ 

                    self.loyalty.rules = rules; 
                    self.loyalty.rules_by_product_id = {};

                    for (var i = 0; i < rules.length; i++){
                        var rule = rules[i];
                        if (!self.loyalty.rules_by_product_id[rule.product_id[0]]) {
                            self.loyalty.rules_by_product_id[rule.product_id[0]] = [rule];
                        } else if (rule.override) {
                            self.loyalty.rules_by_product_id[rule.product_id[0]].unshift(rule);
                        } else {
                            self.loyalty.rules_by_product_id[rule.product_id[0]].push(rule);
                        }
                    }
                },
            },{
                model: 'loyalty.reward',
                condition: function(self){ return !!self.loyalty; },
                fields: ['name','type','minimum_points','gift_product_id','point_cost','discount_product_id','discount'],
                domain: function(self){ return [['loyalty_program_id','=',self.loyalty.id]]; },
                loaded: function(self,rewards){
                    self.loyalty.rewards = rewards; 
                },
            });
        }
    }

    var _super = module.Order;
    module.Order = module.Order.extend({

        /* The total of points won, excluding the points spent on rewards */
        get_won_points: function(){
            if (!this.pos.loyalty || !this.get('client')) {
                return 0;
            }
            
            var orderLines = this.get('orderLines').models;
            var rounding   = this.pos.loyalty.rounding;
            
            var product_sold = 0;
            var total_sold   = 0;
            var total_points = 0;

            for (var i = 0; i < orderLines.length; i++) {
                var line = orderLines[i];
                var product = line.get_product();
                var rules  = this.pos.loyalty.rules_by_product_id[product.id] || [];
                var overriden = false;

                if (line.reward) {  // Reward products are ignored
                    continue;
                }
                
                for (var j = 0; j < rules.length; j++) {
                    var rule = rules[j];
                    total_points += round_pr(line.get_quantity() * rule.pp_product, rounding);
                    total_points += round_pr(line.get_price_with_tax() * rule.pp_currency, rounding);
                    if (rule.override) {
                        overriden = true;
                        break;
                    }
                }

                if (!overriden) {
                    product_sold += line.get_quantity();
                    total_sold   += line.get_price_with_tax();
                }
            }

            total_points += round_pr( total_sold * this.pos.loyalty.pp_currency, rounding );
            total_points += round_pr( product_sold * this.pos.loyalty.pp_product, rounding );
            total_points += round_pr( this.pos.loyalty.pp_order, rounding );

            return total_points;
        },

        /* The total number of points spent on rewards */
        get_spent_points: function() {
            if (!this.pos.loyalty || !this.get('client')) {
                return 0;
            } else {
                var lines    = this.get('orderLines').models;
                var rounding = this.pos.loyalty.rounding;
                var points   = 0;

                for (var i = 0; i < lines.length; i++) {
                    var line = lines[i];
                    if (line.reward) {
                        if (line.reward.type === 'gift') {
                            points += round_pr(line.get_quantity() * line.reward.point_cost, rounding);
                        } else if (line.reward.type === 'discount') {
                            points += round_pr(-line.get_price_with_tax() * line.reward.point_cost, rounding);
                        }
                    }
                }
                return points;
            }
        },

        /* The total number of points lost or won after the order is validated */
        get_new_points: function() {
            if (!this.pos.loyalty || !this.get('client')) {
                return 0;
            } else { 
                return round_pr(this.get_won_points() - this.get_spent_points(), this.pos.loyalty.rounding);
            }
        },

        /* The total number of points that the customer will have after this order is validated */
        get_new_total_points: function() {
            if (!this.pos.loyalty || !this.get('client')) {
                return 0;
            } else { 
                return round_pr(this.get('client').loyalty_points + this.get_new_points(), this.pos.loyalty.rounding);
            }
        },

        /* The number of loyalty points currently owned by the customer */
        get_current_points: function(){
            return this.get('client') ? this.get('client').loyalty_points : 0;
        },

        /* The total number of points spendable on rewards */
        get_spendable_points: function(){
            if (!this.pos.loyalty || !this.get('client')) {
                return 0;
            } else {
                return round_pr(this.get('client').loyalty_points - this.get_spent_points(), this.pos.loyalty.rounding);
            }
        },

        /* The list of rewards that the current customer can get */
        get_available_rewards: function(){
            var client = this.get('client');
            if (!client) {
                return [];
            } 

            var rewards = [];
            for (var i = 0; i < this.pos.loyalty.rewards.length; i++) {
                var reward = this.pos.loyalty.rewards[i];
                if (reward.minimum_points > this.get_spendable_points()) {
                    continue;
                } else if(reward.type === 'gift' && reward.point_cost > this.get_spendable_points()) {
                    continue;
                } 
                rewards.push(reward);
            }
            return rewards;
        },

        apply_reward: function(reward){
            var client = this.get('client');
            if (!client) {
                return;
            } else if (reward.type === 'gift') {
                var product = this.pos.db.get_product_by_id(reward.gift_product_id[0]);
                if (!product) {
                    this.pos.pos_widget.screen_selector.show_popup('error',{
                        'message':'Configuration Error',
                        'comment':'The product associated with the reward "'+reward.name+'" could not be found. Make sure it is available for sale in the point of sale.',
                    });
                    return;
                }

                var line = this.addProduct(product, { 
                    price: 0, 
                    quantity: 1, 
                    merge: false, 
                    extras: { reward: reward },
                });

            } else if (reward.type === 'discount') {
                
                var lrounding = this.pos.loyalty.rounding;
                var crounding = this.pos.currency.rounding;
                var spendable = this.get_spendable_points();
                var order_total = this.getTotalTaxIncluded();
                var discount    = round_pr(order_total * reward.discount,crounding);

                if ( round_pr(discount * reward.point_cost,lrounding) > spendable ) { 
                    discount = round_pr(Math.floor( spendable / reward.point_cost ), crounding);
                }

                var product   = this.pos.db.get_product_by_id(reward.discount_product_id[0]);
                if (!product) {
                    this.pos.pos_widget.screen_selector.show_popup('error',{
                        'message':'Configuration Error',
                        'comment':'The product associated with the reward "'+reward.name+'" could not be found. Make sure it is available for sale in the point of sale.',
                    });
                    return;
                }

                var line = this.addProduct(product, { 
                    price: -discount, 
                    quantity: 1, 
                    merge: false,
                    extras: { reward: reward },
                });
            }
        },
            
        validate: function(){
            var client = this.get('client');
            if ( client ) {
                client.loyalty_points = this.get_new_total_points();
            }
            _super.prototype.validate.apply(this,arguments);
        },
        export_for_printing: function(){
            var json = _super.prototype.export_for_printing.apply(this,arguments);
            json.loyalty_points = this.get_new_points();
            return json;
        },
        export_as_JSON: function(){
            var json = _super.prototype.export_as_JSON.apply(this,arguments);
            json.loyalty_points = this.get_new_points();
            return json;
        },
    });

    module.PosWidget.include({
        loyalty_reward_click: function(){
            var self = this;
            var order  = this.pos.get('selectedOrder');
            var client = order.get('client'); 
            if (!client) {
                this.screen_selector.set_current_screen('clientlist');
                return;
            }

            var rewards = order.get_available_rewards();
            if (rewards.length === 0) {
                this.screen_selector.show_popup('error',{
                    'message': 'No Rewards Available',
                    'comment': 'There are no rewards available for this customer as part of the loyalty program',
                });
                return;
            } else if (rewards.length === 1 && this.pos.loyalty.rewards.length === 1) {
                order.apply_reward(rewards[0]);
                return;
            } else { 
                var list = [];
                for (var i = 0; i < rewards.length; i++) {
                    list.push({
                        label: rewards[i].name,
                        item:  rewards[i],
                    });
                }
                this.screen_selector.show_popup('selection',{
                    'message': 'Please select a reward',
                    'list': list,
                    'confirm': function(reward){
                        order.apply_reward(reward);
                    },
                });
            }
        },

        build_widgets: function(){
            var self = this;
            this._super();
            
            if(this.pos.loyalty && this.pos.loyalty.rewards.length ){
                var button = $(QWeb.render('LoyaltyButton'));
                button.click(function(){ self.loyalty_reward_click(); });
                button.appendTo(this.$('.control-buttons'));
                this.$('.control-buttons').removeClass('oe_hidden');
            }

        },
    });

    module.OrderWidget.include({
        update_summary: function(){
            this._super();

            var order = this.pos.get_order();

            var $loypoints = $(this.el).find('.summary .loyalty-points');

            if(this.pos.loyalty && order.get_client()){
                var points_won      = order.get_won_points();
                var points_spent    = order.get_spent_points();
                var points_total    = order.get_new_total_points(); 
                $loypoints.replaceWith($(QWeb.render('LoyaltyPoints',{ 
                    widget: this, 
                    rounding: this.pos.loyalty.rounding,
                    points_won: points_won,
                    points_spent: points_spent,
                    points_total: points_total,
                })));
                $loypoints = $(this.el).find('.summary .loyalty-points');
                $loypoints.removeClass('oe_hidden');

                if(points_total < 0){
                    $loypoints.addClass('negative');
                }else{
                    $loypoints.removeClass('negative');
                }
            }else{
                $loypoints.empty();
                $loypoints.addClass('oe_hidden');
            }
        },
    });
};

    
