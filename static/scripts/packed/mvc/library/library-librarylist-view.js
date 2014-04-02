define(["galaxy.masthead","mvc/base-mvc","utils/utils","libs/toastr","mvc/library/library-model","mvc/library/library-libraryrow-view"],function(b,g,d,e,c,a){var f=Backbone.View.extend({el:"#libraries_element",events:{"click .edit_library_btn":"edit_button_event","click .save_library_btn":"save_library_modification","click .cancel_library_btn":"cancel_library_modification","click .delete_library_btn":"delete_library","click .undelete_library_btn":"undelete_library","click .sort-libraries-link":"sort_clicked"},modal:null,collection:null,rowViews:{},initialize:function(){var h=this;this.rowViews={};this.collection=new c.Libraries();this.collection.fetch({success:function(i){h.render()},error:function(j,i){e.error("An error occured. Please try again.")}})},render:function(i){var j=this.templateLibraryList();var k=null;var h=true;var h=Galaxy.libraries.preferences.get("with_deleted");var l=null;if(typeof i!=="undefined"){h=typeof i.with_deleted!=="undefined"?i.with_deleted:false;l=typeof i.models!=="undefined"?i.models:null}if(this.collection!==null&&l===null){if(h){k=this.collection.models}else{k=this.collection.where({deleted:false})}}else{if(l!==null){k=l}else{k=[]}}this.$el.html(j({length:k.length,order:Galaxy.libraries.preferences.get("sort_order")}));this.renderRows(k);$("#center [data-toggle]").tooltip();$("#center").css("overflow","auto")},renderRows:function(m){for(var l=0;l<m.length;l++){var k=m[l];var j=_.findWhere(this.rowViews,{id:k.get("id")});if(j!==undefined){this.$el.find("#library_list_body").append(j.el)}else{var h=new a.LibraryRowView(k);this.$el.find("#library_list_body").append(h.el);this.rowViews[k.get("id")]=h}}},sort_clicked:function(){if(Galaxy.libraries.preferences.get("sort_order")==="asc"){this.sortLibraries("name","desc");Galaxy.libraries.preferences.set({sort_order:"desc"})}else{this.sortLibraries("name","asc");Galaxy.libraries.preferences.set({sort_order:"asc"})}this.render()},sortLibraries:function(i,h){if(i==="name"){if(h==="asc"){this.collection.comparator=function(k,j){if(k.get("name").toLowerCase()>j.get("name").toLowerCase()){return 1}if(j.get("name").toLowerCase()>k.get("name").toLowerCase()){return -1}return 0}}else{if(h==="desc"){this.collection.comparator=function(k,j){if(k.get("name").toLowerCase()>j.get("name").toLowerCase()){return -1}if(j.get("name").toLowerCase()>k.get("name").toLowerCase()){return 1}return 0}}}this.collection.sort()}},templateLibraryList:function(){tmpl_array=[];tmpl_array.push('<div class="library_container table-responsive">');tmpl_array.push("<% if(length === 0) { %>");tmpl_array.push("<div>I see no libraries. Why don't you create one?</div>");tmpl_array.push("<% } else{ %>");tmpl_array.push('<table class="grid table table-condensed">');tmpl_array.push("   <thead>");tmpl_array.push('     <th style="width:30%;"><a class="sort-libraries-link" title="Click to reverse order" href="#">name</a> <span title="Sorted alphabetically" class="fa fa-sort-alpha-<%- order %>"></span></th>');tmpl_array.push('     <th style="width:22%;">description</th>');tmpl_array.push('     <th style="width:22%;">synopsis</th> ');tmpl_array.push('     <th style="width:26%;"></th> ');tmpl_array.push("   </thead>");tmpl_array.push('   <tbody id="library_list_body">');tmpl_array.push("   </tbody>");tmpl_array.push("</table>");tmpl_array.push("<% }%>");tmpl_array.push("</div>");return _.template(tmpl_array.join(""))},templateNewLibraryInModal:function(){tmpl_array=[];tmpl_array.push('<div id="new_library_modal">');tmpl_array.push("   <form>");tmpl_array.push('       <input type="text" name="Name" value="" placeholder="Name">');tmpl_array.push('       <input type="text" name="Description" value="" placeholder="Description">');tmpl_array.push('       <input type="text" name="Synopsis" value="" placeholder="Synopsis">');tmpl_array.push("   </form>");tmpl_array.push("</div>");return tmpl_array.join("")},save_library_modification:function(k){var j=$(k.target).closest("tr");var h=this.collection.get(j.data("id"));var i=false;var m=j.find(".input_library_name").val();if(typeof m!=="undefined"&&m!==h.get("name")){if(m.length>2){h.set("name",m);i=true}else{e.warning("Library name has to be at least 3 characters long");return}}var l=j.find(".input_library_description").val();if(typeof l!=="undefined"&&l!==h.get("description")){h.set("description",l);i=true}var n=j.find(".input_library_synopsis").val();if(typeof n!=="undefined"&&n!==h.get("synopsis")){h.set("synopsis",n);i=true}if(i){h.save(null,{patch:true,success:function(o){e.success("Changes to library saved");Galaxy.libraries.libraryListView.toggle_library_modification(j)},error:function(p,o){e.error("An error occured during updating the library :(")}})}},edit_button_event:function(h){this.toggle_library_modification($(h.target).closest("tr"))},toggle_library_modification:function(k){var h=this.collection.get(k.data("id"));k.find(".public_lib_ico").toggle();k.find(".deleted_lib_ico").toggle();k.find(".edit_library_btn").toggle();k.find(".upload_library_btn").toggle();k.find(".permission_library_btn").toggle();k.find(".save_library_btn").toggle();k.find(".cancel_library_btn").toggle();if(h.get("deleted")){}else{k.find(".delete_library_btn").toggle()}if(k.find(".edit_library_btn").is(":hidden")){var i=h.get("name");var m='<input type="text" class="form-control input_library_name" placeholder="name">';k.children("td").eq(0).html(m);if(typeof i!==undefined){k.find(".input_library_name").val(i)}var j=h.get("description");var m='<input type="text" class="form-control input_library_description" placeholder="description">';k.children("td").eq(1).html(m);if(typeof j!==undefined){k.find(".input_library_description").val(j)}var l=h.get("synopsis");var m='<input type="text" class="form-control input_library_synopsis" placeholder="synopsis">';k.children("td").eq(2).html(m);if(typeof l!==undefined){k.find(".input_library_synopsis").val(l)}}else{k.children("td").eq(0).html(h.get("name"));k.children("td").eq(1).html(h.get("description"));k.children("td").eq(2).html(h.get("synopsis"))}},cancel_library_modification:function(j){var i=$(j.target).closest("tr");var h=this.collection.get(i.data("id"));this.toggle_library_modification(i);i.children("td").eq(0).html(h.get("name"));i.children("td").eq(1).html(h.get("description"));i.children("td").eq(2).html(h.get("synopsis"))},undelete_library:function(j){var i=$(j.target).closest("tr");var h=this.collection.get(i.data("id"));this.toggle_library_modification(i);h.url=h.urlRoot+h.id+"?undelete=true";h.destroy({success:function(k){k.set("deleted",false);Galaxy.libraries.libraryListView.collection.add(k);i.removeClass("active");e.success("Library has been undeleted")},error:function(){e.error("An error occured while undeleting the library :(")}})},delete_library:function(j){var i=$(j.target).closest("tr");var h=this.collection.get(i.data("id"));this.toggle_library_modification(i);h.destroy({success:function(k){i.remove();k.set("deleted",true);Galaxy.libraries.libraryListView.collection.add(k);e.success("Library has been marked deleted")},error:function(){e.error("An error occured during deleting the library :(")}})},redirectToHome:function(){window.location="../"},redirectToLogin:function(){window.location="/user/login"},show_library_modal:function(i){i.preventDefault();i.stopPropagation();var h=this;this.modal=Galaxy.modal;this.modal.show({closing_events:true,title:"Create New Library",body:this.templateNewLibraryInModal(),buttons:{Create:function(){h.create_new_library_event()},Close:function(){h.modal.hide()}}})},create_new_library_event:function(){var j=this.serialize_new_library();if(this.validate_new_library(j)){var i=new c.Library();var h=this;i.save(j,{success:function(k){h.collection.add(k);h.modal.hide();h.clear_library_modal();h.render();e.success("Library created")},error:function(){e.error("An error occured :(")}})}else{e.error("Library's name is missing")}return false},clear_library_modal:function(){$("input[name='Name']").val("");$("input[name='Description']").val("");$("input[name='Synopsis']").val("")},serialize_new_library:function(){return{name:$("input[name='Name']").val(),description:$("input[name='Description']").val(),synopsis:$("input[name='Synopsis']").val()}},validate_new_library:function(h){return h.name!==""}});return{LibraryListView:f}});