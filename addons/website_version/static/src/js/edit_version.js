(function() {
    'use strict';
    var hash = "#advanced-view-editor";
    var _t = openerp._t;
    
    var website=openerp.website;

    website.action= {};
    
    website.EditorBar.include({
        start: function() {
            var self = this;
            this.$el.on('click', '#save_as_new_version', function() {
                
                var wizardA = $(openerp.qweb.render("website_version.new_version",{'default_name': moment().format('L')}));
                wizardA.appendTo($('body')).modal({"keyboard" :true});
                wizardA.on('click','.o_create', function(){
                    wizardA.find('.o_message').remove();
                    var version_name = wizardA.find('.o_version_name').val();
                    if(version_name.length == 0){
                        wizardA.find(".o_version_name").after("<p class='o_message' style='color : red'> *"+_t("This field is required")+"</p>");
                    }
                    else{
                        wizardA.modal("hide");
                        openerp.jsonRpc( '/website_version/create_version', 'call', { 'name': version_name, 'version_id': 0}).then(function (result) {
                            $('html').data('version_id', result);
                            var wizard = $(openerp.qweb.render("website_version.dialogue",{message:_.str.sprintf("You are now working on version: %s.", version_name),
                                                                                       dialogue:_.str.sprintf("If you edit this page or others, all changes will be recorded in the version. It will not be visible by visitors until you publish the version.")}));
                            wizard.appendTo($('body')).modal({"keyboard" :true});
                            wizard.on('click','.o_confirm', function(){
                                self.save();
                            });
                            wizard.on('hidden.bs.modal', function () {$(this).remove();});
                        }).fail(function(){
                            var wizard = $(openerp.qweb.render("website_version.message",{message:_t("This name already exists.")}));
                            wizard.appendTo($('body')).modal({"keyboard" :true});
                            wizard.on('hidden.bs.modal', function () {$(this).remove();});
                        });
                    }
                });
                wizardA.on('hidden.bs.modal', function () {$(this).remove();});
            
            });
            this.$el.on('click', '#save_and_publish', function() {
                var version_id = parseInt($('html').data('version_id'));
                if(version_id)
                {
                    self.save();
                }
                else
                {
                    var wizard = $(openerp.qweb.render("website_version.publish",{message:_t("Are you sure you want to publish your modifications.")}));
                    wizard.appendTo($('body')).modal({"keyboard" :true});
                    wizard.on('click','.o_confirm', function(){
                        self.save();
                    });
                    wizard.on('hidden.bs.modal', function () {$(this).remove();});
                }

            });

            $('.option_choice').click(function() {
                self.$el.find(".o_second_choice").remove();
                var name = $('#version-menu-button').data('version_name');
                if(name){
                    self.$el.find(".o_first_choice").before(openerp.qweb.render("all_options", {version:'Save on '+name}));
                }
                else{
                    self.$el.find(".o_first_choice").before(openerp.qweb.render("all_options", {version:'Save and Publish'}));
                }

            });
            
            return this._super();
        }
    });

    
})();