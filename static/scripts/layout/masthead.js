define(["utils/utils","layout/menu","layout/scratchbook","mvc/user/user-quotameter"],function(a,b,c,d){var e=Backbone.View.extend({el_masthead:"#everything",options:null,$background:null,list:[],initialize:function(a){this.options=a,$("body").off(),this.setElement($(this._template(a))),$("#masthead").replaceWith(this.$el),this.$background=$(this.el).find("#masthead-background");var e=this;$(window).on("click",function(a){var b=$(a.target).closest("a[download]");1==b.length&&(0===$("iframe[id=download]").length&&$("body").append($('<iframe id="download" style="display: none;" />')),$("iframe[id=download]").attr("src",b.attr("href")),a.preventDefault())}).on("beforeunload",function(){var a="";for(var b in e.list)if(e.list[b].options.onbeforeunload){var c=e.list[b].options.onbeforeunload();c&&(a+=c+" ")}return""!==a?a:void 0}),this.menu=Galaxy.menu=new b.GalaxyMenu({masthead:this,config:this.options}),this.frame=Galaxy.frame=new c.GalaxyFrame({masthead:this}),Galaxy.quotaMeter=new d.UserQuotaMeter({model:Galaxy.user,el:this.$(".quota-meter-container")}).render()},events:{click:"_click",mousedown:function(a){a.preventDefault()}},append:function(a){return this._add(a,!0)},prepend:function(a){return this._add(a,!1)},highlight:function(a){var b=$(this.el).find("#"+a+"> li");b&&b.addClass("active")},_add:function(a,b){var c=$(this.el).find("#"+a.location);if(c){var d=$(a.el);d.addClass("masthead-item"),b?c.append(d):c.prepend(d),this.list.push(a)}return null},_click:function(a){var b=$(this.el).find(".popup");b&&b.hide();var c=$(a.target).closest(".masthead-item").find(".popup");$(a.target).hasClass("head")?(c.show(),this.$background.show()):this.$background.hide()},_template:function(a){var b=a.brand?"/ "+a.brand:"";return'<div><div id="masthead" class="navbar navbar-fixed-top navbar-inverse"><div style="position: relative; right: -50%; float: left;"><div id="navbar" style="display: block; position: relative; right: 50%;"></div></div><div class="navbar-brand"><a href="'+a.logo_url+'"><img style="margin-left: 0.35em;" border="0" src="'+Galaxy.root+'static/images/galaxyIcon_noText.png"><span id="brand"> Galaxy '+b+'</span></a></div><div class="quota-meter-container"></div><div id="iconbar" class="iconbar"></div></div><div id="masthead-background" style="display: none; position: absolute; top: 33px; width: 100%; height: 100%; z-index: 1010"></div></div>'}});return{GalaxyMasthead:e}});
//# sourceMappingURL=../../maps/layout/masthead.js.map