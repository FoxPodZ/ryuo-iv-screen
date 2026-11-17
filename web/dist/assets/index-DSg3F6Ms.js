(function(){let e=document.createElement(`link`).relList;if(e&&e.supports&&e.supports(`modulepreload`))return;for(let e of document.querySelectorAll(`link[rel="modulepreload"]`))n(e);new MutationObserver(e=>{for(let t of e)if(t.type===`childList`)for(let e of t.addedNodes)e.tagName===`LINK`&&e.rel===`modulepreload`&&n(e)}).observe(document,{childList:!0,subtree:!0});function t(e){let t={};return e.integrity&&(t.integrity=e.integrity),e.referrerPolicy&&(t.referrerPolicy=e.referrerPolicy),t.credentials=e.crossOrigin===`use-credentials`?`include`:e.crossOrigin===`anonymous`?`omit`:`same-origin`,t}function n(e){if(e.ep)return;e.ep=!0;let n=t(e);fetch(e.href,n)}})();var e=globalThis,t=e.ShadowRoot&&(e.ShadyCSS===void 0||e.ShadyCSS.nativeShadow)&&`adoptedStyleSheets`in Document.prototype&&`replace`in CSSStyleSheet.prototype,n=Symbol(),r=new WeakMap,i=class{constructor(e,t,r){if(this._$cssResult$=!0,r!==n)throw Error("CSSResult is not constructable. Use `unsafeCSS` or `css` instead.");this.cssText=e,this.t=t}get styleSheet(){let e=this.o,n=this.t;if(t&&e===void 0){let t=n!==void 0&&n.length===1;t&&(e=r.get(n)),e===void 0&&((this.o=e=new CSSStyleSheet).replaceSync(this.cssText),t&&r.set(n,e))}return e}toString(){return this.cssText}},a=e=>new i(typeof e==`string`?e:e+``,void 0,n),o=(e,...t)=>new i(e.length===1?e[0]:t.reduce((t,n,r)=>t+(e=>{if(!0===e._$cssResult$)return e.cssText;if(typeof e==`number`)return e;throw Error(`Value passed to 'css' function must be a 'css' function result: `+e+`. Use 'unsafeCSS' to pass non-literal values, but take care to ensure page security.`)})(n)+e[r+1],e[0]),e,n),s=(n,r)=>{if(t)n.adoptedStyleSheets=r.map(e=>e instanceof CSSStyleSheet?e:e.styleSheet);else for(let t of r){let r=document.createElement(`style`),i=e.litNonce;i!==void 0&&r.setAttribute(`nonce`,i),r.textContent=t.cssText,n.appendChild(r)}},c=t?e=>e:e=>e instanceof CSSStyleSheet?(e=>{let t=``;for(let n of e.cssRules)t+=n.cssText;return a(t)})(e):e,{is:l,defineProperty:u,getOwnPropertyDescriptor:ee,getOwnPropertyNames:te,getOwnPropertySymbols:ne,getPrototypeOf:re}=Object,d=globalThis,ie=d.trustedTypes,ae=ie?ie.emptyScript:``,oe=d.reactiveElementPolyfillSupport,f=(e,t)=>e,p={toAttribute(e,t){switch(t){case Boolean:e=e?ae:null;break;case Object:case Array:e=e==null?e:JSON.stringify(e)}return e},fromAttribute(e,t){let n=e;switch(t){case Boolean:n=e!==null;break;case Number:n=e===null?null:Number(e);break;case Object:case Array:try{n=JSON.parse(e)}catch{n=null}}return n}},se=(e,t)=>!l(e,t),ce={attribute:!0,type:String,converter:p,reflect:!1,useDefault:!1,hasChanged:se};Symbol.metadata??=Symbol(`metadata`),d.litPropertyMetadata??=new WeakMap;var m=class extends HTMLElement{static addInitializer(e){this._$Ei(),(this.l??=[]).push(e)}static get observedAttributes(){return this.finalize(),this._$Eh&&[...this._$Eh.keys()]}static createProperty(e,t=ce){if(t.state&&(t.attribute=!1),this._$Ei(),this.prototype.hasOwnProperty(e)&&((t=Object.create(t)).wrapped=!0),this.elementProperties.set(e,t),!t.noAccessor){let n=Symbol(),r=this.getPropertyDescriptor(e,n,t);r!==void 0&&u(this.prototype,e,r)}}static getPropertyDescriptor(e,t,n){let{get:r,set:i}=ee(this.prototype,e)??{get(){return this[t]},set(e){this[t]=e}};return{get:r,set(t){let a=r?.call(this);i?.call(this,t),this.requestUpdate(e,a,n)},configurable:!0,enumerable:!0}}static getPropertyOptions(e){return this.elementProperties.get(e)??ce}static _$Ei(){if(this.hasOwnProperty(f(`elementProperties`)))return;let e=re(this);e.finalize(),e.l!==void 0&&(this.l=[...e.l]),this.elementProperties=new Map(e.elementProperties)}static finalize(){if(this.hasOwnProperty(f(`finalized`)))return;if(this.finalized=!0,this._$Ei(),this.hasOwnProperty(f(`properties`))){let e=this.properties,t=[...te(e),...ne(e)];for(let n of t)this.createProperty(n,e[n])}let e=this[Symbol.metadata];if(e!==null){let t=litPropertyMetadata.get(e);if(t!==void 0)for(let[e,n]of t)this.elementProperties.set(e,n)}this._$Eh=new Map;for(let[e,t]of this.elementProperties){let n=this._$Eu(e,t);n!==void 0&&this._$Eh.set(n,e)}this.elementStyles=this.finalizeStyles(this.styles)}static finalizeStyles(e){let t=[];if(Array.isArray(e)){let n=new Set(e.flat(1/0).reverse());for(let e of n)t.unshift(c(e))}else e!==void 0&&t.push(c(e));return t}static _$Eu(e,t){let n=t.attribute;return!1===n?void 0:typeof n==`string`?n:typeof e==`string`?e.toLowerCase():void 0}constructor(){super(),this._$Ep=void 0,this.isUpdatePending=!1,this.hasUpdated=!1,this._$Em=null,this._$Ev()}_$Ev(){this._$ES=new Promise(e=>this.enableUpdating=e),this._$AL=new Map,this._$E_(),this.requestUpdate(),this.constructor.l?.forEach(e=>e(this))}addController(e){(this._$EO??=new Set).add(e),this.renderRoot!==void 0&&this.isConnected&&e.hostConnected?.()}removeController(e){this._$EO?.delete(e)}_$E_(){let e=new Map,t=this.constructor.elementProperties;for(let n of t.keys())this.hasOwnProperty(n)&&(e.set(n,this[n]),delete this[n]);e.size>0&&(this._$Ep=e)}createRenderRoot(){let e=this.shadowRoot??this.attachShadow(this.constructor.shadowRootOptions);return s(e,this.constructor.elementStyles),e}connectedCallback(){this.renderRoot??=this.createRenderRoot(),this.enableUpdating(!0),this._$EO?.forEach(e=>e.hostConnected?.())}enableUpdating(e){}disconnectedCallback(){this._$EO?.forEach(e=>e.hostDisconnected?.())}attributeChangedCallback(e,t,n){this._$AK(e,n)}_$ET(e,t){let n=this.constructor.elementProperties.get(e),r=this.constructor._$Eu(e,n);if(r!==void 0&&!0===n.reflect){let i=(n.converter?.toAttribute===void 0?p:n.converter).toAttribute(t,n.type);this._$Em=e,i==null?this.removeAttribute(r):this.setAttribute(r,i),this._$Em=null}}_$AK(e,t){let n=this.constructor,r=n._$Eh.get(e);if(r!==void 0&&this._$Em!==r){let e=n.getPropertyOptions(r),i=typeof e.converter==`function`?{fromAttribute:e.converter}:e.converter?.fromAttribute===void 0?p:e.converter;this._$Em=r;let a=i.fromAttribute(t,e.type);this[r]=a??this._$Ej?.get(r)??a,this._$Em=null}}requestUpdate(e,t,n,r=!1,i){if(e!==void 0){let a=this.constructor;if(!1===r&&(i=this[e]),n??=a.getPropertyOptions(e),!((n.hasChanged??se)(i,t)||n.useDefault&&n.reflect&&i===this._$Ej?.get(e)&&!this.hasAttribute(a._$Eu(e,n))))return;this.C(e,t,n)}!1===this.isUpdatePending&&(this._$ES=this._$EP())}C(e,t,{useDefault:n,reflect:r,wrapped:i},a){n&&!(this._$Ej??=new Map).has(e)&&(this._$Ej.set(e,a??t??this[e]),!0!==i||a!==void 0)||(this._$AL.has(e)||(this.hasUpdated||n||(t=void 0),this._$AL.set(e,t)),!0===r&&this._$Em!==e&&(this._$Eq??=new Set).add(e))}async _$EP(){this.isUpdatePending=!0;try{await this._$ES}catch(e){Promise.reject(e)}let e=this.scheduleUpdate();return e!=null&&await e,!this.isUpdatePending}scheduleUpdate(){return this.performUpdate()}performUpdate(){if(!this.isUpdatePending)return;if(!this.hasUpdated){if(this.renderRoot??=this.createRenderRoot(),this._$Ep){for(let[e,t]of this._$Ep)this[e]=t;this._$Ep=void 0}let e=this.constructor.elementProperties;if(e.size>0)for(let[t,n]of e){let{wrapped:e}=n,r=this[t];!0!==e||this._$AL.has(t)||r===void 0||this.C(t,void 0,n,r)}}let e=!1,t=this._$AL;try{e=this.shouldUpdate(t),e?(this.willUpdate(t),this._$EO?.forEach(e=>e.hostUpdate?.()),this.update(t)):this._$EM()}catch(t){throw e=!1,this._$EM(),t}e&&this._$AE(t)}willUpdate(e){}_$AE(e){this._$EO?.forEach(e=>e.hostUpdated?.()),this.hasUpdated||(this.hasUpdated=!0,this.firstUpdated(e)),this.updated(e)}_$EM(){this._$AL=new Map,this.isUpdatePending=!1}get updateComplete(){return this.getUpdateComplete()}getUpdateComplete(){return this._$ES}shouldUpdate(e){return!0}update(e){this._$Eq&&=this._$Eq.forEach(e=>this._$ET(e,this[e])),this._$EM()}updated(e){}firstUpdated(e){}};m.elementStyles=[],m.shadowRootOptions={mode:`open`},m[f(`elementProperties`)]=new Map,m[f(`finalized`)]=new Map,oe?.({ReactiveElement:m}),(d.reactiveElementVersions??=[]).push(`2.1.2`);var h=globalThis,le=e=>e,g=h.trustedTypes,ue=g?g.createPolicy(`lit-html`,{createHTML:e=>e}):void 0,de=`$lit$`,_=`lit$${Math.random().toFixed(9).slice(2)}$`,fe=`?`+_,pe=`<${fe}>`,v=document,y=()=>v.createComment(``),b=e=>e===null||typeof e!=`object`&&typeof e!=`function`,x=Array.isArray,me=e=>x(e)||typeof e?.[Symbol.iterator]==`function`,he=`[ 	
\f\r]`,S=/<(?:(!--|\/[^a-zA-Z])|(\/?[a-zA-Z][^>\s]*)|(\/?$))/g,ge=/-->/g,_e=/>/g,C=RegExp(`>|${he}(?:([^\\s"'>=/]+)(${he}*=${he}*(?:[^ \t\n\f\r"'\`<>=]|("|')|))|$)`,`g`),ve=/'/g,ye=/"/g,be=/^(?:script|style|textarea|title)$/i,w=(e=>(t,...n)=>({_$litType$:e,strings:t,values:n}))(1),T=Symbol.for(`lit-noChange`),E=Symbol.for(`lit-nothing`),xe=new WeakMap,D=v.createTreeWalker(v,129);function Se(e,t){if(!x(e)||!e.hasOwnProperty(`raw`))throw Error(`invalid template strings array`);return ue===void 0?t:ue.createHTML(t)}var Ce=(e,t)=>{let n=e.length-1,r=[],i,a=t===2?`<svg>`:t===3?`<math>`:``,o=S;for(let t=0;t<n;t++){let n=e[t],s,c,l=-1,u=0;for(;u<n.length&&(o.lastIndex=u,c=o.exec(n),c!==null);)u=o.lastIndex,o===S?c[1]===`!--`?o=ge:c[1]===void 0?c[2]===void 0?c[3]!==void 0&&(o=C):(be.test(c[2])&&(i=RegExp(`</`+c[2],`g`)),o=C):o=_e:o===C?c[0]===`>`?(o=i??S,l=-1):c[1]===void 0?l=-2:(l=o.lastIndex-c[2].length,s=c[1],o=c[3]===void 0?C:c[3]===`"`?ye:ve):o===ye||o===ve?o=C:o===ge||o===_e?o=S:(o=C,i=void 0);let ee=o===C&&e[t+1].startsWith(`/>`)?` `:``;a+=o===S?n+pe:l>=0?(r.push(s),n.slice(0,l)+de+n.slice(l)+_+ee):n+_+(l===-2?t:ee)}return[Se(e,a+(e[n]||`<?>`)+(t===2?`</svg>`:t===3?`</math>`:``)),r]},O=class e{constructor({strings:t,_$litType$:n},r){let i;this.parts=[];let a=0,o=0,s=t.length-1,c=this.parts,[l,u]=Ce(t,n);if(this.el=e.createElement(l,r),D.currentNode=this.el.content,n===2||n===3){let e=this.el.content.firstChild;e.replaceWith(...e.childNodes)}for(;(i=D.nextNode())!==null&&c.length<s;){if(i.nodeType===1){if(i.hasAttributes())for(let e of i.getAttributeNames())if(e.endsWith(de)){let t=u[o++],n=i.getAttribute(e).split(_),r=/([.?@])?(.*)/.exec(t);c.push({type:1,index:a,name:r[2],strings:n,ctor:r[1]===`.`?Te:r[1]===`?`?Ee:r[1]===`@`?De:j}),i.removeAttribute(e)}else e.startsWith(_)&&(c.push({type:6,index:a}),i.removeAttribute(e));if(be.test(i.tagName)){let e=i.textContent.split(_),t=e.length-1;if(t>0){i.textContent=g?g.emptyScript:``;for(let n=0;n<t;n++)i.append(e[n],y()),D.nextNode(),c.push({type:2,index:++a});i.append(e[t],y())}}}else if(i.nodeType===8){if(i.data===fe)c.push({type:2,index:a});else{let e=-1;for(;(e=i.data.indexOf(_,e+1))!==-1;)c.push({type:7,index:a}),e+=_.length-1}}a++}}static createElement(e,t){let n=v.createElement(`template`);return n.innerHTML=e,n}};function k(e,t,n=e,r){if(t===T)return t;let i=r===void 0?n._$Cl:n._$Co?.[r],a=b(t)?void 0:t._$litDirective$;return i?.constructor!==a&&(i?._$AO?.(!1),a===void 0?i=void 0:(i=new a(e),i._$AT(e,n,r)),r===void 0?n._$Cl=i:(n._$Co??=[])[r]=i),i!==void 0&&(t=k(e,i._$AS(e,t.values),i,r)),t}var we=class{constructor(e,t){this._$AV=[],this._$AN=void 0,this._$AD=e,this._$AM=t}get parentNode(){return this._$AM.parentNode}get _$AU(){return this._$AM._$AU}u(e){let{el:{content:t},parts:n}=this._$AD,r=(e?.creationScope??v).importNode(t,!0);D.currentNode=r;let i=D.nextNode(),a=0,o=0,s=n[0];for(;s!==void 0;){if(a===s.index){let t;s.type===2?t=new A(i,i.nextSibling,this,e):s.type===1?t=new s.ctor(i,s.name,s.strings,this,e):s.type===6&&(t=new Oe(i,this,e)),this._$AV.push(t),s=n[++o]}a!==s?.index&&(i=D.nextNode(),a++)}return D.currentNode=v,r}p(e){let t=0;for(let n of this._$AV)n!==void 0&&(n.strings===void 0?n._$AI(e[t]):(n._$AI(e,n,t),t+=n.strings.length-2)),t++}},A=class e{get _$AU(){return this._$AM?._$AU??this._$Cv}constructor(e,t,n,r){this.type=2,this._$AH=E,this._$AN=void 0,this._$AA=e,this._$AB=t,this._$AM=n,this.options=r,this._$Cv=r?.isConnected??!0}get parentNode(){let e=this._$AA.parentNode,t=this._$AM;return t!==void 0&&e?.nodeType===11&&(e=t.parentNode),e}get startNode(){return this._$AA}get endNode(){return this._$AB}_$AI(e,t=this){e=k(this,e,t),b(e)?e===E||e==null||e===``?(this._$AH!==E&&this._$AR(),this._$AH=E):e!==this._$AH&&e!==T&&this._(e):e._$litType$===void 0?e.nodeType===void 0?me(e)?this.k(e):this._(e):this.T(e):this.$(e)}O(e){return this._$AA.parentNode.insertBefore(e,this._$AB)}T(e){this._$AH!==e&&(this._$AR(),this._$AH=this.O(e))}_(e){this._$AH!==E&&b(this._$AH)?this._$AA.nextSibling.data=e:this.T(v.createTextNode(e)),this._$AH=e}$(e){let{values:t,_$litType$:n}=e,r=typeof n==`number`?this._$AC(e):(n.el===void 0&&(n.el=O.createElement(Se(n.h,n.h[0]),this.options)),n);if(this._$AH?._$AD===r)this._$AH.p(t);else{let e=new we(r,this),n=e.u(this.options);e.p(t),this.T(n),this._$AH=e}}_$AC(e){let t=xe.get(e.strings);return t===void 0&&xe.set(e.strings,t=new O(e)),t}k(t){x(this._$AH)||(this._$AH=[],this._$AR());let n=this._$AH,r,i=0;for(let a of t)i===n.length?n.push(r=new e(this.O(y()),this.O(y()),this,this.options)):r=n[i],r._$AI(a),i++;i<n.length&&(this._$AR(r&&r._$AB.nextSibling,i),n.length=i)}_$AR(e=this._$AA.nextSibling,t){for(this._$AP?.(!1,!0,t);e!==this._$AB;){let t=le(e).nextSibling;le(e).remove(),e=t}}setConnected(e){this._$AM===void 0&&(this._$Cv=e,this._$AP?.(e))}},j=class{get tagName(){return this.element.tagName}get _$AU(){return this._$AM._$AU}constructor(e,t,n,r,i){this.type=1,this._$AH=E,this._$AN=void 0,this.element=e,this.name=t,this._$AM=r,this.options=i,n.length>2||n[0]!==``||n[1]!==``?(this._$AH=Array(n.length-1).fill(new String),this.strings=n):this._$AH=E}_$AI(e,t=this,n,r){let i=this.strings,a=!1;if(i===void 0)e=k(this,e,t,0),a=!b(e)||e!==this._$AH&&e!==T,a&&(this._$AH=e);else{let r=e,o,s;for(e=i[0],o=0;o<i.length-1;o++)s=k(this,r[n+o],t,o),s===T&&(s=this._$AH[o]),a||=!b(s)||s!==this._$AH[o],s===E?e=E:e!==E&&(e+=(s??``)+i[o+1]),this._$AH[o]=s}a&&!r&&this.j(e)}j(e){e===E?this.element.removeAttribute(this.name):this.element.setAttribute(this.name,e??``)}},Te=class extends j{constructor(){super(...arguments),this.type=3}j(e){this.element[this.name]=e===E?void 0:e}},Ee=class extends j{constructor(){super(...arguments),this.type=4}j(e){this.element.toggleAttribute(this.name,!!e&&e!==E)}},De=class extends j{constructor(e,t,n,r,i){super(e,t,n,r,i),this.type=5}_$AI(e,t=this){if((e=k(this,e,t,0)??E)===T)return;let n=this._$AH,r=e===E&&n!==E||e.capture!==n.capture||e.once!==n.once||e.passive!==n.passive,i=e!==E&&(n===E||r);r&&this.element.removeEventListener(this.name,this,n),i&&this.element.addEventListener(this.name,this,e),this._$AH=e}handleEvent(e){typeof this._$AH==`function`?this._$AH.call(this.options?.host??this.element,e):this._$AH.handleEvent(e)}},Oe=class{constructor(e,t,n){this.element=e,this.type=6,this._$AN=void 0,this._$AM=t,this.options=n}get _$AU(){return this._$AM._$AU}_$AI(e){k(this,e)}},ke={M:de,P:_,A:fe,C:1,L:Ce,R:we,D:me,V:k,I:A,H:j,N:Ee,U:De,B:Te,F:Oe},Ae=h.litHtmlPolyfillSupport;Ae?.(O,A),(h.litHtmlVersions??=[]).push(`3.3.3`);var je=(e,t,n)=>{let r=n?.renderBefore??t,i=r._$litPart$;if(i===void 0){let e=n?.renderBefore??null;r._$litPart$=i=new A(t.insertBefore(y(),e),e,void 0,n??{})}return i._$AI(e),i},M=globalThis,N=class extends m{constructor(){super(...arguments),this.renderOptions={host:this},this._$Do=void 0}createRenderRoot(){let e=super.createRenderRoot();return this.renderOptions.renderBefore??=e.firstChild,e}update(e){let t=this.render();this.hasUpdated||(this.renderOptions.isConnected=this.isConnected),super.update(e),this._$Do=je(t,this.renderRoot,this.renderOptions)}connectedCallback(){super.connectedCallback(),this._$Do?.setConnected(!0)}disconnectedCallback(){super.disconnectedCallback(),this._$Do?.setConnected(!1)}render(){return T}};N._$litElement$=!0,N.finalized=!0,M.litElementHydrateSupport?.({LitElement:N});var Me=M.litElementPolyfillSupport;Me?.({LitElement:N}),(M.litElementVersions??=[]).push(`4.2.2`);var P=e=>(t,n)=>{n===void 0?customElements.define(e,t):n.addInitializer(()=>{customElements.define(e,t)})},Ne={attribute:!0,type:String,converter:p,reflect:!1,hasChanged:se},Pe=(e=Ne,t,n)=>{let{kind:r,metadata:i}=n,a=globalThis.litPropertyMetadata.get(i);if(a===void 0&&globalThis.litPropertyMetadata.set(i,a=new Map),r===`setter`&&((e=Object.create(e)).wrapped=!0),a.set(n.name,e),r===`accessor`){let{name:r}=n;return{set(n){let i=t.get.call(this);t.set.call(this,n),this.requestUpdate(r,i,e,!0,n)},init(t){return t!==void 0&&this.C(r,void 0,e,t),t}}}if(r===`setter`){let{name:r}=n;return function(n){let i=this[r];t.call(this,n),this.requestUpdate(r,i,e,!0,n)}}throw Error(`Unsupported decorator location: `+r)};function F(e){return(t,n)=>typeof n==`object`?Pe(e,t,n):((e,t,n)=>{let r=t.hasOwnProperty(n);return t.constructor.createProperty(n,e),r?Object.getOwnPropertyDescriptor(t,n):void 0})(e,t,n)}function I(e){return F({...e,state:!0,attribute:!1})}var Fe=[`Single`,`Random`,`Cycle`],Ie=e=>({media:e.media.map(e=>[...e]),playback_modes:[...e.playback_modes]});function Le(e,t,n){let r=[...e],[i]=r.splice(t,1);return r.splice(n,0,i),r}var Re=e=>/\.(mp4|gif|png|jpe?g)$/i.exec(e.name)?.[1].toLowerCase()??null,L=`/api/v1`,ze=(e,t)=>`${L}/media/preview/${e}/${encodeURIComponent(t)}`,R=e=>`/profiles/${encodeURIComponent(e)}`,Be=e=>`${L}${R(e)}/export`,z=class extends Error{constructor(e,t,n){super(n),this.name=`ApiError`,this.status=e,this.code=t}};async function Ve(e){let t={};try{t=await e.json()}catch{}if(!e.ok){let n=typeof t.error==`string`?t.error:`http_error`,r=typeof t.message==`string`?t.message:`confirmed`in t&&typeof t.error==`string`?t.error:`HTTP ${e.status}`;throw new z(e.status,n,r)}return t}var He=class{constructor(){this.csrfToken=null}setCsrfToken(e){this.csrfToken=e}async request(e,t={}){let n=new Headers(t.headers);return n.set(`Accept`,`application/json`),this.csrfToken&&t.method&&![`GET`,`HEAD`,`OPTIONS`].includes(t.method.toUpperCase())&&n.set(`X-CSRF-Token`,this.csrfToken),Ve(await fetch(`${L}${e}`,{...t,headers:n,credentials:`same-origin`}))}async authStatus(){let e=await this.request(`/auth/status`);return this.setCsrfToken(e.csrfToken),e}async login(e){let t=await this.request(`/auth/login`,{method:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify({password:e})});return this.setCsrfToken(t.csrfToken),t}async loadSnapshot(){let[e,t,n]=await Promise.all([this.request(`/state`),this.request(`/telemetry`),this.request(`/device`)]);return{revision:e.revision,state:e.state,telemetry:t,device:n}}async loadSensors(){return this.request(`/sensors`)}async loadMedia(){let{factory:e,custom:t,tools:n,adb:r}=await this.request(`/media`);return{factory:e,custom:t,tools:n,adb:{available:r.available,reason:r.reason}}}async deleteMedia(e){return this.request(`/media/${encodeURIComponent(e)}`,{method:`DELETE`})}uploadMedia(e,t,n){let r=Re(e);if(!r)throw Error(`Выберите файл MP4, GIF, PNG или JPG`);let i=new XMLHttpRequest;i.open(`POST`,`${L}/media/upload`),i.setRequestHeader(`Content-Type`,`application/octet-stream`),i.setRequestHeader(`Accept`,`application/json`),i.setRequestHeader(`X-Filename`,`upload.${r}`),this.csrfToken&&i.setRequestHeader(`X-CSRF-Token`,this.csrfToken);let a=!0;return{result:new Promise((r,o)=>{i.upload.addEventListener(`progress`,e=>{a&&t(e.lengthComputable&&e.total>0?100*e.loaded/e.total:null)}),i.upload.addEventListener(`load`,()=>{a=!1,n()}),i.addEventListener(`load`,()=>{a=!1;let e={};try{e=JSON.parse(i.responseText)??{}}catch{}i.status>=200&&i.status<300&&e.confirmed===!0&&typeof e.name==`string`&&e.name.length>0?r(e):o(new z(i.status,`upload_failed`,e.message||e.error||`Сервер не подтвердил загрузку (HTTP ${i.status})`))}),i.addEventListener(`error`,()=>o(Error(`Связь с сервером прервалась`))),i.addEventListener(`abort`,()=>o(new DOMException(`Передача отменена`,`AbortError`))),i.send(e)}),cancel:()=>{a&&i.abort()}}}async loadDiagnostics(){return this.request(`/diagnostics`)}async loadProfiles(){return(await this.request(`/profiles`)).profiles}async writeProfile(e,t,n=``){let r={create:`/profiles`,import:`/profiles/import`,rename:R(n),update:R(n),duplicate:`${R(n)}/duplicate`}[e];return(await this.request(r,{method:e===`rename`||e===`update`?`PATCH`:`POST`,headers:{"Content-Type":`application/json`},body:JSON.stringify(t)})).profile}async deleteProfile(e){await this.request(R(e),{method:`DELETE`})}async applyProfile(e,t){return this.request(`${R(e)}/apply`,{method:`POST`,headers:{"Content-Type":`application/json`,"If-Match":String(t)},body:JSON.stringify({revision:t})})}async patchState(e,t,n){return this.request(`/${e}`,{method:`PATCH`,headers:{"Content-Type":`application/json`,"If-Match":String(t)},body:JSON.stringify({revision:t,...n})})}};function Ue(e){let t=null,n=[];for(let r of e.split(`
`))if(r.startsWith(`id:`)){let e=Number.parseInt(r.slice(3).trim(),10);Number.isSafeInteger(e)&&e>=0&&(t=e)}else r.startsWith(`data:`)&&n.push(r.slice(5).trimStart());if(t===null||n.length===0)return null;let r=JSON.parse(n.join(`
`));return{id:t,snapshot:r}}var We=class{connect(e,t,n){let r=new AbortController;return this.pump(r,e,t).catch(e=>{r.signal.aborted||n(e)}),{close:()=>r.abort()}}async pump(e,t,n){let r=new Headers({Accept:`text/event-stream`});t!==null&&r.set(`Last-Event-ID`,String(t));let i=await fetch(`${L}/events`,{credentials:`same-origin`,headers:r,signal:e.signal,cache:`no-store`});if(!i.ok){await Ve(i);return}if(!i.body)throw Error(`Сервер не открыл поток событий`);let a=i.body.getReader(),o=new TextDecoder,s=``;for(;!e.signal.aborted;){let{done:e,value:t}=await a.read();if(e)break;s+=o.decode(t,{stream:!0}).replace(/\r\n/g,`
`);let r=s.indexOf(`

`);for(;r>=0;){let e=Ue(s.slice(0,r));s=s.slice(r+2),e&&n(e.id,e.snapshot),r=s.indexOf(`

`)}}if(!e.signal.aborted)throw Error(`Поток событий закрыт сервером`)}},Ge=e=>{if(typeof e==`object`&&e&&!Object.isFrozen(e)){for(let t of Object.values(e))Ge(t);Object.freeze(e)}return e},Ke=()=>({phase:`loading`,auth:null,csrfToken:null,snapshot:null,error:null,connected:!1,lastEventId:0,retryDelay:500,sensors:[],mutationError:null}),B=e=>e instanceof Error?e.message:`Неизвестная ошибка`,qe=class{constructor(e,t,n=(e,t)=>window.setTimeout(e,t),r=e=>window.clearTimeout(e)){this.api=e,this.events=t,this.schedule=n,this.cancelSchedule=r,this.state=Ge(Ke()),this.listeners=new Set,this.connection=null,this.retryToken=0,this.stopped=!1,this.sessionTimer=null,this.sessionGeneration=0,this.transfer=null,this.resourceRequests={media:0,profiles:0,diagnostics:0}}get value(){return this.state}subscribe(e){return this.listeners.add(e),e(this.state),()=>this.listeners.delete(e)}update(e){this.state=Ge({...this.state,...e});for(let e of this.listeners)e(this.state)}async start(){this.stopped=!1,this.clearSessionExpiry(),this.connection?.close(),this.connection=null,this.resetLibrary(),this.update({phase:`loading`,error:null,connected:!1});try{let e=await this.api.authStatus(),t=this.applyAuth(e);if(e.required&&!e.authenticated){this.update({phase:`login`});return}if(!t)return;await this.loadAndConnect(this.sessionGeneration)}catch(e){this.handleLoadError(e)}}stop(){this.stopped=!0,this.resetLibrary(),this.retryToken+=1,this.clearSessionExpiry(),this.connection?.close(),this.connection=null,this.update({connected:!1})}async login(e){this.update({error:null});try{let t=await this.api.login(e);if(!this.applyAuth(t))return;this.update({phase:`loading`}),await this.loadAndConnect(this.sessionGeneration)}catch(e){this.handleLoadError(e,!0)}}async ensureSensors(e=!1){if(!e&&(this.state.sensors?.length??0)>0||!this.api.loadSensors)return;let t=this.sessionGeneration;try{let e=await this.api.loadSensors();!this.stopped&&t===this.sessionGeneration&&this.update({sensors:e.sensors,mutationError:e.error})}catch(e){!this.stopped&&t===this.sessionGeneration&&this.update({mutationError:`Не удалось загрузить датчики: ${B(e)}`})}}async loadMedia(){await this.loadLibrary(`media`,()=>this.api.loadMedia?.())}async loadProfiles(){await this.loadLibrary(`profiles`,()=>this.api.loadProfiles?.())}async loadDiagnostics(){await this.loadLibrary(`diagnostics`,()=>this.api.loadDiagnostics?.())}async loadLibrary(e,t){let n=this.sessionGeneration,r=++this.resourceRequests[e],i=`${e}Error`,a=()=>!this.stopped&&n===this.sessionGeneration&&r===this.resourceRequests[e];try{let n=await t();a()&&this.update({[e]:n,[i]:null})}catch(e){if(!a())return;e instanceof z&&e.status===401?this.handleLoadError(e):this.update({[i]:B(e)})}}async deleteMedia(e){if(!this.api.deleteMedia||!this.state.media?.custom.includes(e)||this.state.media.factory.includes(e))throw Error(`Можно удалить только пользовательский файл`);let t=await this.api.deleteMedia(e);if(t.confirmed!==!0)throw Error(t.error||`Сервер не подтвердил удаление`);await this.loadMedia()}async uploadMedia(e){if(!this.api.uploadMedia||!this.state.media?.adb.available||this.transfer)return;let t=this.sessionGeneration,n=()=>!this.stopped&&t===this.sessionGeneration;this.update({upload:{phase:`uploading`,percent:null}});try{this.transfer=this.api.uploadMedia(e,e=>{n()&&this.update({upload:{phase:`uploading`,percent:e}})},()=>{n()&&this.update({upload:{phase:`processing`}})});let t=await this.transfer.result;if(!n())return;if(t.confirmed!==!0||!t.name)throw Error(`Сервер не подтвердил загрузку`);this.update({upload:{phase:`confirmed`,name:t.name}}),this.loadMedia()}catch(e){if(!n())return;e instanceof z&&e.status===401?this.handleLoadError(e):this.update({upload:e instanceof DOMException&&e.name===`AbortError`?{phase:`cancelled`}:{phase:`error`,message:B(e)}})}finally{n()&&(this.transfer=null)}}cancelUpload(){this.state.upload?.phase===`uploading`&&this.transfer?.cancel()}async writeProfile(e,t,n){if(!this.api.writeProfile)throw Error(`API профилей недоступен`);await this.api.writeProfile(e,t,n),await this.loadProfiles()}async deleteProfile(e){if(!this.api.deleteProfile)throw Error(`API профилей недоступен`);await this.api.deleteProfile(e),await this.loadProfiles()}async applyProfile(e,t){return this.mutateState(()=>this.api.applyProfile?.(e,t))}async patchScreen(e,t,n=this.state.snapshot?.revision){return this.mutateState(()=>n===void 0?void 0:this.api.patchState?.(e,n,t))}async mutateState(e){let t=this.sessionGeneration,n=()=>!this.stopped&&t===this.sessionGeneration,r=e=>{let t=this.state.snapshot;return t&&(!e||t.revision>e.revision)?t:e};try{let t=await e();if(!t)throw Error(`Редактор ещё не получил текущее состояние`);let i=await this.api.loadSnapshot();if(!n())return{ok:!1,conflict:!1,error:null};let a=r(i);if(!t.saved||!t.queued||t.error){let e=t.error||`Состояние сохранено, но команда не поставлена в очередь`;return this.update({snapshot:a,mutationError:e}),{ok:!1,conflict:!1,error:e}}return this.update({snapshot:a,mutationError:null,error:null}),{ok:!0,conflict:!1,error:null}}catch(e){if(!n())return{ok:!1,conflict:!1,error:null};if(e instanceof z&&e.status===401&&this.handleLoadError(e),e instanceof z&&e.status===409){let e=this.state.snapshot,t=!1;try{e=await this.api.loadSnapshot(),t=!0}catch{}let i=t?`Конфликт ревизий: загружено актуальное состояние`:`Конфликт ревизий: не удалось загрузить актуальное состояние`;return n()&&this.update({snapshot:r(e),mutationError:i}),{ok:!1,conflict:!0,error:i}}let t=`Изменение не применено: ${B(e)}`;return this.update({mutationError:t}),{ok:!1,conflict:!1,error:t}}}resetLibrary(){this.cancelUpload(),this.transfer=null,this.update({media:void 0,profiles:void 0,diagnostics:void 0,upload:void 0,mediaError:null,profilesError:null,diagnosticsError:null,sensors:[]})}async loadAndConnect(e){let t=await this.api.loadSnapshot();this.stopped||e!==this.sessionGeneration||(this.update({phase:`ready`,snapshot:t,error:null}),this.openEvents())}handleLoadError(e,t=!1){e instanceof z&&e.status===401?(this.clearSessionExpiry(),this.api.setCsrfToken?.(null),this.resetLibrary(),this.connection?.close(),this.connection=null,this.update({phase:`login`,connected:!1,error:B(e),auth:{required:!0,authenticated:!1,csrfToken:null},csrfToken:null})):this.update({phase:t?`login`:`error`,connected:!1,error:B(e)})}applyAuth(e){if(this.clearSessionExpiry(),this.api.setCsrfToken?.(e.csrfToken),this.update({auth:e,csrfToken:e.csrfToken}),!e.required||!e.authenticated)return!0;let t=e.expiresIn;if(typeof t!=`number`||!Number.isFinite(t)||t<=0)return this.expireSession(this.sessionGeneration),!1;let n=this.sessionGeneration;return this.sessionTimer=this.schedule(()=>this.expireSession(n),t*1e3),!0}clearSessionExpiry(){this.sessionGeneration+=1,this.sessionTimer!==null&&this.cancelSchedule(this.sessionTimer),this.sessionTimer=null}expireSession(e){this.stopped||e!==this.sessionGeneration||(this.sessionGeneration+=1,this.sessionTimer=null,this.retryToken+=1,this.connection?.close(),this.connection=null,this.api.setCsrfToken?.(null),this.resetLibrary(),this.update({phase:`login`,auth:{required:!0,authenticated:!1,csrfToken:null,expiresIn:0},csrfToken:null,connected:!1,error:`Сессия истекла. Войдите снова.`}))}openEvents(){if(this.stopped)return;this.connection?.close();let e=this.state.lastEventId>0?this.state.lastEventId:null;this.connection=this.events.connect(e,(e,t)=>this.acceptEvent(e,t),e=>this.handleEventError(e))}acceptEvent(e,t){!Number.isSafeInteger(e)||e<=this.state.lastEventId||this.state.snapshot&&t.revision<this.state.snapshot.revision||this.update({phase:`ready`,snapshot:t,error:null,connected:!0,lastEventId:e,retryDelay:500})}handleEventError(e){if(this.connection?.close(),this.connection=null,e instanceof z&&e.status===401){this.handleLoadError(e);return}let t=this.state.retryDelay;this.update({connected:!1,error:B(e),retryDelay:Math.min(t*2,1e4)});let n=++this.retryToken;this.schedule(()=>{!this.stopped&&n===this.retryToken&&this.openEvents()},t)}};function V(e,t,n,r){var i=arguments.length,a=i<3?t:r===null?r=Object.getOwnPropertyDescriptor(t,n):r,o;if(typeof Reflect==`object`&&typeof Reflect.decorate==`function`)a=Reflect.decorate(e,t,n,r);else for(var s=e.length-1;s>=0;s--)(o=e[s])&&(a=(i<3?o(a):i>3?o(t,n,a):o(t,n))||a);return i>3&&a&&Object.defineProperty(t,n,a),a}var Je={"cpu.temperature":`CPU`,"cpu.power":`CPU Power`,"gpu.temperature":`GPU`,"gpu.vram.used":`VRAM`,"gpu.power":`GPU Power`,"fan.cpu":`CPU Fan`,"fan.gpu":`GPU Fan`},Ye=e=>Number.isInteger(e)?String(e):e.toFixed(1),Xe=e=>{if(!e.available||e.value===null)return`Недоступно`;let t=e.value;return e.unit===`B`||e.unit===`bytes`?`${(t/1024**3).toFixed(1)} GiB`:e.unit===`C`?`${Ye(t)} °C`:e.unit===`F`?`${Ye(t)} °F`:`${Ye(t)} ${e.unit}`.trim()},Ze=(e=0)=>`${Math.floor(e/3600)}ч ${Math.floor(e%3600/60)}м`,Qe=class extends N{static{this.styles=o`
    :host { display: block; color: var(--ink, #f5f7fb); }
    .notice { margin: 0 0 1rem; padding: .8rem 1rem; border: 1px solid #eb5c9a66; border-radius: .8rem; background: #eb5c9a16; color: #ffc8df; }
    .loading { min-height: 40vh; display: grid; place-items: center; color: #a9b3c4; letter-spacing: .08em; text-transform: uppercase; }
    .error-state { min-height: 40vh; display: grid; place-content: center; gap: .6rem; text-align: center; }
    .error-state h1 { color: #ffc2d8; }
    .error-state p { color: #a9b3c4; }
    .hero { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(15rem, .65fr); gap: 1rem; margin-bottom: 1rem; }
    .panel { border: 1px solid #ffffff12; border-radius: 1rem; padding: 1.2rem; background: linear-gradient(145deg, #171b27e8, #0e111aee); box-shadow: 0 1rem 3rem #0006; }
    .device { position: relative; overflow: hidden; }
    .device::after { content: ""; position: absolute; inset: auto -10% -65% 45%; aspect-ratio: 1; border-radius: 50%; background: radial-gradient(circle, #54e8d64a, transparent 65%); pointer-events: none; }
    .eyebrow { color: #65e5d7; text-transform: uppercase; letter-spacing: .14em; font-size: .72rem; font-weight: 700; }
    h1, h2, p { margin: 0; }
    h1 { margin-top: .45rem; font-size: clamp(1.6rem, 3vw, 2.7rem); line-height: 1; }
    h2 { margin-bottom: 1rem; font-size: 1rem; color: #c7cfdb; }
    .status { display: inline-flex; align-items: center; gap: .45rem; margin-top: .8rem; color: #b9c5d6; }
    .dot { width: .55rem; height: .55rem; border-radius: 50%; background: #5de3b1; box-shadow: 0 0 1rem #5de3b1; }
    .dot.offline { background: #f2647f; box-shadow: 0 0 1rem #f2647f; }
    dl { display: grid; grid-template-columns: 1fr auto; gap: .55rem 1rem; margin: 0; }
    dt { color: #8591a5; }
    dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(11.5rem, 1fr)); gap: .8rem; }
    .metric { min-height: 7.5rem; display: flex; flex-direction: column; justify-content: space-between; }
    .metric strong { font-size: 1.5rem; font-variant-numeric: tabular-nums; }
    .metric small { color: #8591a5; overflow-wrap: anywhere; }
    .unavailable strong { color: #f0a9c3; font-size: 1rem; }
    .screen { margin-top: 1rem; }
    .media { color: #dce4f0; overflow-wrap: anywhere; }
    @media (max-width: 720px) { .hero { grid-template-columns: 1fr; } .panel { padding: 1rem; } }
    @media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; transition: none !important; } }
  `}render(){let e=this.view?.snapshot;if(!e&&this.view?.phase===`error`)return w`
      <section class="panel error-state" role="alert">
        <h1>Не удалось загрузить Dashboard</h1>
        <p>${this.view.error||`API недоступен`}</p>
        <p>Повторите попытку или проверьте состояние службы ryuo-screen.</p>
      </section>
    `;if(!e)return w`<div class="loading" role="status">Загрузка телеметрии…</div>`;let{device:t,state:n,telemetry:r}=e;return w`
      ${this.view.error?w`<div class="notice" role="alert">${this.view.error}</div>`:E}
      <section aria-label="Сводка системы">
        <div class="hero">
          <section class="panel device" aria-label="Устройство">
            <span class="eyebrow">ROG Ryuo IV · Live</span>
            <h1>${t.model||`Ryuo IV`}</h1>
            <div class="status"><span class="dot ${t.connected?``:`offline`}"></span>${t.connected?`Подключено`:`Нет соединения`} · ${t.health}</div>
          </section>
          <section class="panel" aria-label="Состояние демона">
            <h2>Daemon / HID</h2>
            <dl>
              <dt>Firmware</dt><dd>${t.firmware||`—`}</dd>
              <dt>Uptime</dt><dd>${Ze(t.uptime)}</dd>
              <dt>Last ACK</dt><dd>${t.last_ack??`—`}</dd>
              <dt>Reconnects</dt><dd>${t.reconnect_count??0}</dd>
            </dl>
          </section>
        </div>
        <section aria-label="Телеметрия">
          <h2>Live telemetry</h2>
          <div class="grid">
            ${Object.entries(r.measurements).map(([e,t])=>w`
              <article class="panel metric ${t.available?``:`unavailable`}">
                <span class="eyebrow">${Je[e]||e}</span>
                <strong>${Xe(t)}</strong>
                <small>${t.available?t.source||`Источник не указан`:t.error||`Нет данных от датчика`}</small>
              </article>
            `)}
          </div>
        </section>
        <section class="panel screen" aria-label="Текущая конфигурация экрана">
          <h2>Screen state</h2>
          <dl>
            <dt>Profile</dt><dd>${n.active_profile||`Без профиля`}</dd>
            <dt>Layout</dt><dd>${n.screen_mode}</dd>
            <dt>Brightness</dt><dd>${n.brightness}%</dd>
            <dt>Media</dt><dd class="media">${n.media.flat().join(` · `)||`Не выбрано`}</dd>
          </dl>
        </section>
      </section>
    `}};V([F({attribute:!1})],Qe.prototype,`view`,void 0),Qe=V([P(`dashboard-page`)],Qe);var $e=class extends N{static{this.styles=o`
    :host { display: block; min-height: 70vh; display: grid; place-items: center; color: #f5f7fb; }
    .card { width: min(24rem, calc(100vw - 2rem)); padding: 1.6rem; border: 1px solid #ffffff16; border-radius: 1.2rem; background: #121722e8; box-shadow: 0 1.5rem 4rem #0008; }
    .mark { color: #61e5d6; text-transform: uppercase; font-size: .72rem; font-weight: 800; letter-spacing: .15em; }
    h1 { margin: .55rem 0 .5rem; font-size: 1.8rem; }
    p { color: #98a4b6; line-height: 1.5; }
    label { display: grid; gap: .45rem; margin-top: 1.2rem; color: #cdd4df; }
    input { color: #fff; background: #080b12; border: 1px solid #ffffff24; border-radius: .7rem; padding: .8rem; font: inherit; }
    input:focus-visible, button:focus-visible { outline: 3px solid #66e5d7; outline-offset: 2px; }
    button { width: 100%; margin-top: .85rem; padding: .8rem; border: 0; border-radius: .7rem; color: #07110f; background: linear-gradient(90deg, #5ce4d3, #79f0b6); font: inherit; font-weight: 800; cursor: pointer; }
    [role=alert] { color: #ffc2d8; padding: .7rem; border-radius: .6rem; background: #f2558c18; }
  `}render(){return!this.view||this.view.phase!==`login`||!this.view.auth?.required?E:w`
      <section class="card" aria-labelledby="login-title">
        <span class="mark">Ryuo Control</span>
        <h1 id="login-title">Вход в LAN-панель</h1>
        <p>Пароль проверяется локальным сервисом и не сохраняется в интерфейсе.</p>
        ${this.view.error?w`<p role="alert">${this.view.error}</p>`:E}
        <form @submit=${this.submit}>
          <label>Пароль<input type="password" name="password" autocomplete="current-password" required></label>
          <button type="submit">Войти</button>
        </form>
      </section>
    `}submit(e){e.preventDefault();let t=e.currentTarget.elements.namedItem(`password`),n=t.value;t.value=``,this.dispatchEvent(new CustomEvent(`login-submit`,{detail:{password:n},bubbles:!0,composed:!0}))}};V([F({attribute:!1})],$e.prototype,`view`,void 0),$e=V([P(`login-view`)],$e);var et=()=>({enabled:!1,measurement_id:``,widget:``,label:null}),tt=e=>({...e}),H=e=>{if(e.length>6)throw RangeError(`screen editor supports exactly six slots`);let t=e.map(tt);for(;t.length<6;)t.push(et());return t},nt=(e,t,n)=>{let r=H(e);if(!Number.isInteger(t)||!Number.isInteger(n)||t<0||t>=6||n<0||n>=6)throw RangeError(`slot position must be between zero and five`);let[i]=r.splice(t,1);return r.splice(n,0,i),r},U=(e,t)=>e[0]??t,rt=(e,t)=>t===`Screen Splitting`?{...e,screen_mode:t,media:[[...e.media[0]??[]],[...e.media[1]??[]]],playback_modes:[U(e.playback_modes,`Single`),e.playback_modes[1]??`Single`],title_colors:[U(e.title_colors,`#E5252B`),e.title_colors[1]??U(e.title_colors,`#E5252B`)],content_colors:[U(e.content_colors,`#FFFFFF`),e.content_colors[1]??U(e.content_colors,`#FFFFFF`)]}:{...e,screen_mode:`Full Screen`,media:[[...e.media[0]??[]]],playback_modes:[U(e.playback_modes,`Single`)],title_colors:[U(e.title_colors,`#E5252B`)],content_colors:[U(e.content_colors,`#FFFFFF`)]},it=Object.freeze({"cpu.load":`CPU Load`,"cpu.usage":`CPU Usage`,"cpu.temperature":`CPU Temperature`,"cpu.frequency":`CPU Speed Average`,"cpu.voltage":`CPU Voltage`,"gpu.load":`GPU Load`,"gpu.usage":`GPU Usage`,"gpu.temperature":`GPU Temperature`,"gpu.clock.core":`GPU Speed`,"gpu.power":`GPU Power`,"gpu.voltage":`GPU Voltage`,"memory.load":`Memory Utilization`,"memory.frequency":`Memory Frequency`,"disk.temperature":`Hard Disk Temperature`,"motherboard.temperature":`Motherboard Temperature`}),at=e=>e.flatMap(e=>{let t=e.measurementId.startsWith(`fan.`)&&e.unit===`RPM`,n=t?`Fan Speed ${e.label}`:it[e.measurementId];return n?[{descriptor:e,widget:n,available:e.available,userLabelCapable:t}]:[]}),ot=e=>({...e,media:e.media.map(e=>[...e]),playback_modes:[...e.playback_modes],slots:H(e.slots),title_colors:[...e.title_colors],content_colors:[...e.content_colors],sensor_selectors:{...e.sensor_selectors}}),st=class extends N{static{this.styles=o`
    :host { display: block; }
    figure { margin: 0; display: grid; gap: .65rem; }
    figcaption { color: #aeb9c9; font-size: .78rem; }
    .panel { aspect-ratio: 2240 / 1080; display: grid; grid-template-columns: 1fr; overflow: hidden; border: .55rem solid #202838; border-radius: 1.2rem; background: #070a11; box-shadow: inset 0 0 3rem #000, 0 1rem 2.5rem #0005; opacity: calc(var(--preview-opacity, 100) / 100); }
    .panel.split { grid-template-columns: 1fr 1fr; }
    .zone { display: grid; grid-template-columns: repeat(3, 1fr); gap: .35rem; padding: .7rem; border-right: 1px solid #ffffff18; background: radial-gradient(circle at 25% 0%, #153f4c, transparent 60%); }
    .slot { display: grid; place-content: center; min-width: 0; padding: .3rem; border-radius: .45rem; background: #111827c9; color: #fff; text-align: center; font-size: clamp(.5rem, 1.2vw, .78rem); overflow-wrap: anywhere; }
    .slot.off { opacity: .25; }
  `}render(){if(!this.state)return w``;let e=this.state.screen_mode===`Screen Splitting`,t=e?[this.state.slots.slice(0,3),this.state.slots.slice(3,6)]:[this.state.slots];return w`
      <figure aria-label="Предпросмотр расположения виджетов">
        <div class="panel ${e?`split`:``}" style=${`--preview-opacity:${this.state.opacity}`}>
          ${t.map(e=>w`<div class="zone">
            ${e.map(e=>w`<div class="slot ${e.enabled?``:`off`}">${e.enabled?e.label||e.widget:`Пусто`}</div>`)}
          </div>`)}
        </div>
        <figcaption>Предпросмотр конфигурации — не снимок экрана</figcaption>
      </figure>
    `}};V([F({attribute:!1})],st.prototype,`state`,void 0),st=V([P(`device-preview`)],st);var ct=32,W=class extends N{constructor(...e){super(...e),this.assignment={enabled:!1,measurement_id:``,widget:``,label:null},this.options=[],this.index=0}static{this.styles=o`
    :host { display: block; }
    article { display: grid; gap: .55rem; padding: .8rem; border: 1px solid #ffffff16; border-radius: .8rem; background: #0c111bd9; }
    header { display: flex; align-items: center; justify-content: space-between; gap: .5rem; }
    strong { color: #67e5d7; }
    .moves { display: flex; gap: .3rem; }
    button, select, input { font: inherit; color: #eef4fb; background: #151c29; border: 1px solid #ffffff24; border-radius: .45rem; padding: .45rem; }
    button { min-width: 2rem; cursor: pointer; }
    button:focus-visible, select:focus-visible, input:focus-visible { outline: 2px solid #65e5d7; outline-offset: 2px; }
    label { display: grid; gap: .25rem; color: #a9b4c6; font-size: .82rem; }
    .meta { display: grid; gap: .2rem; color: #8f9bad; font-size: .72rem; overflow-wrap: anywhere; }
    .bad { color: #f2a8c2; }
  `}render(){let e=this.options.find(e=>e.descriptor.measurementId===this.assignment.measurement_id);return w`
      <article draggable="true" @dragstart=${this.onDragStart} @dragover=${this.onDragOver} @drop=${this.onDrop}>
        <header>
          <strong>Слот ${this.index+1}</strong>
          <span class="moves">
            <button type="button" aria-label="Переместить слот ${this.index+1} вверх" ?disabled=${this.index===0} @click=${()=>this.move(-1)}>↑</button>
            <button type="button" aria-label="Переместить слот ${this.index+1} вниз" ?disabled=${this.index===5} @click=${()=>this.move(1)}>↓</button>
          </span>
        </header>
        <label>Датчик
          <select .value=${this.assignment.enabled?this.assignment.measurement_id:``} @change=${this.onSensorChange}>
            <option value="">Отключён — позиция сохранена</option>
            ${this.options.map(e=>w`
              <option value=${e.descriptor.measurementId}>
                ${e.descriptor.label} · ${e.descriptor.ref.provider} · ${e.available?`доступен`:`недоступен`}
              </option>
            `)}
          </select>
        </label>
        ${e?.userLabelCapable?w`
          <label>Пользовательская подпись
            <input name="slot_label" maxlength="32" .value=${this.assignment.label??e.descriptor.label} @change=${this.onLabelChange}>
          </label>
        `:E}
        ${e?w`
          <div class="meta ${e.available?``:`bad`}">
            <span>${e.descriptor.ref.provider} / ${e.descriptor.ref.device}</span>
            <span>${e.descriptor.source||`Источник не указан`}</span>
            ${e.available?E:w`<span>${e.descriptor.error||`Датчик недоступен`}</span>`}
          </div>
        `:E}
      </article>
    `}emit(e,t){this.dispatchEvent(new CustomEvent(e,{detail:t,bubbles:!0,composed:!0}))}move(e){this.emit(`slot-move`,{from:this.index,to:this.index+e})}onDragStart(e){e.dataTransfer?.setData(`text/plain`,String(this.index)),e.dataTransfer&&(e.dataTransfer.effectAllowed=`move`),this.emit(`slot-drag-start`,{index:this.index})}onDragOver(e){e.preventDefault(),e.dataTransfer&&(e.dataTransfer.dropEffect=`move`)}onDrop(e){e.preventDefault(),this.emit(`slot-drop`,{index:this.index})}onSensorChange(e){let t=e.currentTarget.value;if(!t){this.emit(`slot-change`,{index:this.index,assignment:{...this.assignment,enabled:!1}});return}let n=this.options.find(e=>e.descriptor.measurementId===t);if(!n)return;let r=n.descriptor.label.slice(0,ct);this.emit(`slot-change`,{index:this.index,assignment:{enabled:!0,measurement_id:t,widget:n.widget,label:n.userLabelCapable?r:null}})}onLabelChange(e){let t=e.currentTarget.value.trim().slice(0,ct),n=this.options.find(e=>e.descriptor.measurementId===this.assignment.measurement_id);if(!n?.userLabelCapable)return;let r=n.descriptor.label.slice(0,ct);this.emit(`slot-change`,{index:this.index,assignment:{...this.assignment,label:t||r,widget:`Fan Speed ${t||r}`}})}};V([F({attribute:!1})],W.prototype,`assignment`,void 0),V([F({attribute:!1})],W.prototype,`options`,void 0),V([F({type:Number})],W.prototype,`index`,void 0),W=V([P(`sensor-slot`)],W);var lt=()=>({schema_version:1,revision:0,active_profile:null,screen_mode:`Full Screen`,media:[[]],playback_modes:[`Single`],slots:H([]),brightness:85,temperature_unit:`Celsius`,refresh_interval:1,title_colors:[`#E5252B`],content_colors:[`#FFFFFF`],opacity:100,rgb_mode:`off`,rgb_target:`value`,thermal_source:`cpu.temperature`,sensor_selectors:{}}),G=class extends N{constructor(...e){super(...e),this.snapshot=null,this.sensors=[],this.mutationError=null,this.draft=lt(),this.fullRestart=!1,this.dragFrom=null,this.draftRevision=-1,this.patchTimer=null,this.pending=new Map}static{this.styles=o`
    :host { display: block; color: #f5f7fb; }
    .page { display: grid; gap: 1rem; }
    .heading { display: flex; justify-content: space-between; gap: 1rem; align-items: end; }
    h1, h2, p { margin: 0; }
    h1 { font-size: clamp(1.5rem, 3vw, 2.4rem); }
    .muted { color: #91a0b5; }
    .layout { display: grid; grid-template-columns: minmax(19rem, .9fr) minmax(24rem, 1.35fr); gap: 1rem; align-items: start; }
    .panel { border: 1px solid #ffffff14; border-radius: 1rem; padding: 1rem; background: linear-gradient(145deg, #151a27eb, #0d111aee); box-shadow: 0 1rem 2.5rem #0004; }
    .preview { position: sticky; top: 5.5rem; display: grid; gap: 1rem; }
    .controls { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .8rem; }
    fieldset { grid-column: 1 / -1; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .7rem; margin: 0; padding: .8rem; border: 1px solid #ffffff16; border-radius: .8rem; }
    legend { padding: 0 .35rem; color: #67e5d7; }
    label { display: grid; gap: .3rem; color: #aeb9c9; font-size: .82rem; }
    input, select { width: 100%; min-width: 0; padding: .55rem; border: 1px solid #ffffff24; border-radius: .5rem; color: #f5f7fb; background: #111827; font: inherit; }
    input[type="color"] { min-height: 2.65rem; padding: .25rem; }
    input:focus-visible, select:focus-visible { outline: 2px solid #65e5d7; outline-offset: 2px; }
    .slots { display: grid; gap: .65rem; margin-top: .8rem; }
    .alert { padding: .75rem .9rem; border: 1px solid #f26ca066; border-radius: .7rem; color: #ffc8df; background: #ed5d9214; }
    .restart { border-color: #f1b35b66; color: #ffd9a1; background: #e99b3112; }
    @media (max-width: 880px) { .layout { grid-template-columns: 1fr; } .preview { position: static; } }
    @media (max-width: 560px) { .controls, fieldset { grid-template-columns: 1fr; } .heading { align-items: start; flex-direction: column; } }
  `}connectedCallback(){super.connectedCallback(),this.controller?.ensureSensors()}disconnectedCallback(){this.patchTimer!==null&&window.clearTimeout(this.patchTimer),this.patchTimer=null,this.pending.clear(),super.disconnectedCallback()}willUpdate(e){e.has(`snapshot`)&&this.snapshot&&this.snapshot.state.revision!==this.draftRevision&&(this.draft=ot(this.snapshot.state),this.draftRevision=this.snapshot.state.revision,this.fullRestart=!1)}render(){let e=at(this.sensors),t=this.draft.screen_mode===`Screen Splitting`?2:1;return w`
      <section class="page" aria-labelledby="screen-heading">
        <div class="heading">
          <div>
            <p class="muted">Ryuo IV · Screen composer</p>
            <h1 id="screen-heading">Экран и шесть слотов</h1>
          </div>
          <p class="muted">Revision ${this.draft.revision}</p>
        </div>
        ${this.mutationError?w`<div class="alert" role="alert">${this.mutationError}</div>`:E}
        ${this.fullRestart?w`<div class="alert restart" data-full-restart>Изменение media или режима перезапустит воспроизведение полной конфигурацией.</div>`:E}
        <div class="layout">
          <aside class="panel preview" aria-label="Предпросмотр">
            <p class="muted">Предпросмотр конфигурации — не снимок экрана</p>
            <device-preview .state=${this.draft}></device-preview>
            <div class="controls">
              <label>Режим экрана
                <select name="screen_mode" .value=${this.draft.screen_mode} @change=${this.onMode}>
                  <option>Full Screen</option><option>Screen Splitting</option>
                </select>
              </label>
              <label>Яркость
                <input name="brightness" type="range" min="0" max="102" step="1" .value=${String(this.draft.brightness)} @input=${this.onBrightness}>
              </label>
              <label>Единица температуры
                <select name="temperature_unit" .value=${this.draft.temperature_unit} @change=${this.onUnit}>
                  <option>Celsius</option><option>Fahrenheit</option>
                </select>
              </label>
              <label>Интервал, сек
                <input name="refresh_interval" type="number" min="0.1" max="60" step="0.1" .value=${String(this.draft.refresh_interval)} @change=${this.onInterval}>
              </label>
              <label>Прозрачность
                <input name="opacity" type="range" min="0" max="100" step="1" .value=${String(this.draft.opacity)} @input=${this.onOpacity}>
              </label>
              <label>RGB режим
                <select name="rgb_mode" .value=${this.draft.rgb_mode} @change=${this.onRgbMode}>
                  <option value="off">Off</option><option value="hue">Hue</option><option value="thermal">Thermal</option>
                </select>
              </label>
              <label>RGB цель
                <select name="rgb_target" .value=${this.draft.rgb_target} @change=${this.onRgbTarget}>
                  <option value="title">Title</option><option value="value">Value</option><option value="both">Both</option>
                </select>
              </label>
              <label>Thermal source
                <select name="thermal_source" .value=${this.draft.thermal_source} @change=${this.onThermalSource}>
                  ${e.filter(e=>e.descriptor.unit===`°C`||e.descriptor.unit===`C`).map(e=>w`
                    <option value=${e.descriptor.measurementId}>${e.descriptor.label}</option>
                  `)}
                </select>
              </label>
              <fieldset>
                <legend>Цвета зон</legend>
                ${Array.from({length:t},(e,t)=>w`
                  <label>Заголовок ${t+1}<input type="color" name=${`title_color_${t}`} .value=${this.draft.title_colors[t]} @input=${e=>this.onColor(e,`title_colors`,t)}></label>
                  <label>Значение ${t+1}<input type="color" name=${`content_color_${t}`} .value=${this.draft.content_colors[t]} @input=${e=>this.onColor(e,`content_colors`,t)}></label>
                `)}
              </fieldset>
            </div>
          </aside>
          <section class="panel" aria-label="Редактор слотов">
            <h2>Позиции датчиков</h2>
            <p class="muted">Отключение сохраняет позицию. Перетаскивайте карточки или используйте кнопки со стрелками.</p>
            <p class="muted">${e.map(e=>`${e.descriptor.ref.provider}/${e.descriptor.ref.device}: ${e.available?`доступен`:e.descriptor.error||`недоступен`}`).join(` · `)}</p>
            <div class="slots" @slot-change=${this.onSlotChange} @slot-move=${this.onSlotMove} @slot-drag-start=${this.onSlotDragStart} @slot-drop=${this.onSlotDrop}>
              ${this.draft.slots.map((t,n)=>w`
                <sensor-slot
                  aria-label=${`Слот ${n+1}: ${t.enabled?t.label||t.widget:`отключён`}`}
                  .assignment=${t}
                  .options=${e}
                  .index=${n}>
                </sensor-slot>
              `)}
            </div>
          </section>
        </div>
      </section>
    `}queue(e,t){this.pending.set(e,{...this.pending.get(e)??{},...t}),this.patchTimer!==null&&window.clearTimeout(this.patchTimer),this.patchTimer=window.setTimeout(()=>{this.flush()},160)}async flush(){this.patchTimer=null;let e=[...this.pending.entries()];this.pending.clear();for(let[t,n]of e)if(!(await this.controller.patchScreen(t,n)).ok)break}onBrightness(e){let t=Number(e.currentTarget.value);this.draft={...this.draft,brightness:t},this.queue(`brightness`,{brightness:t})}onOpacity(e){let t=Number(e.currentTarget.value);this.draft={...this.draft,opacity:t},this.queue(`screen`,{opacity:t})}onUnit(e){let t=e.currentTarget.value;this.draft={...this.draft,temperature_unit:t},this.queue(`telemetry-settings`,{temperature_unit:t})}onInterval(e){let t=Number(e.currentTarget.value);t>0&&t<=60&&(this.draft={...this.draft,refresh_interval:t},this.queue(`telemetry-settings`,{refresh_interval:t}))}onMode(e){let t=e.currentTarget.value;this.draft=rt(this.draft,t),this.fullRestart=!0,this.queue(`screen`,{screen_mode:this.draft.screen_mode,media:this.draft.media,playback_modes:this.draft.playback_modes,title_colors:this.draft.title_colors,content_colors:this.draft.content_colors})}onColor(e,t,n){let r=[...this.draft[t]];r[n]=e.currentTarget.value.toUpperCase(),this.draft={...this.draft,[t]:r},this.queue(`screen`,{[t]:r})}onRgbMode(e){let t=e.currentTarget.value;this.draft={...this.draft,rgb_mode:t},this.queue(`screen`,{rgb_mode:t})}onRgbTarget(e){let t=e.currentTarget.value;this.draft={...this.draft,rgb_target:t},this.queue(`screen`,{rgb_target:t})}onThermalSource(e){let t=e.currentTarget.value;this.draft={...this.draft,thermal_source:t},this.queue(`screen`,{thermal_source:t})}onSlotChange(e){let t=H(this.draft.slots);t[e.detail.index]={...e.detail.assignment},this.draft={...this.draft,slots:t},this.queue(`screen`,{slots:t})}onSlotMove(e){let t=nt(this.draft.slots,e.detail.from,e.detail.to);this.draft={...this.draft,slots:t},this.queue(`screen`,{slots:t})}onSlotDragStart(e){this.dragFrom=e.detail.index}onSlotDrop(e){if(this.dragFrom===null)return;let t=this.dragFrom;this.dragFrom=null,this.onSlotMove(new CustomEvent(`slot-move`,{detail:{from:t,to:e.detail.index}}))}};V([F({attribute:!1})],G.prototype,`snapshot`,void 0),V([F({attribute:!1})],G.prototype,`sensors`,void 0),V([F({attribute:!1})],G.prototype,`controller`,void 0),V([F({attribute:!1})],G.prototype,`mutationError`,void 0),V([I()],G.prototype,`draft`,void 0),V([I()],G.prototype,`fullRestart`,void 0),G=V([P(`screen-page`)],G);var K={ATTRIBUTE:1,CHILD:2,PROPERTY:3,BOOLEAN_ATTRIBUTE:4,EVENT:5,ELEMENT:6},ut=e=>(...t)=>({_$litDirective$:e,values:t}),dt=class{constructor(e){}get _$AU(){return this._$AM._$AU}_$AT(e,t,n){this._$Ct=e,this._$AM=t,this._$Ci=n}_$AS(e,t){return this.update(e,t)}update(e,t){return this.render(...t)}},{I:ft}=ke,pt=e=>e.strings===void 0,mt={},ht=(e,t=mt)=>e._$AH=t,q=ut(class extends dt{constructor(e){if(super(e),e.type!==K.PROPERTY&&e.type!==K.ATTRIBUTE&&e.type!==K.BOOLEAN_ATTRIBUTE)throw Error("The `live` directive is not allowed on child or event bindings");if(!pt(e))throw Error("`live` bindings can only contain a single expression")}render(e){return e}update(e,[t]){if(t===T||t===E)return t;let n=e.element,r=e.name;if(e.type===K.PROPERTY){if(t===n[r])return T}else if(e.type===K.BOOLEAN_ATTRIBUTE){if(!!t===n.hasAttribute(r))return T}else if(e.type===K.ATTRIBUTE&&n.getAttribute(r)===t+``)return T;return ht(e),t}}),J=o`
  :host { display: block; color: #f5f7fb; }
  *, *::before, *::after { box-sizing: border-box; }
  .page, .stack { display: grid; gap: 1rem; min-width: 0; }
  .columns { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; align-items: start; }
  .panel { min-width: 0; padding: clamp(.9rem, 2vw, 1.3rem); border: 1px solid #ffffff20; border-radius: 1rem; background: linear-gradient(145deg, #171b27, #10141e); }
  .row, .actions { display: flex; align-items: center; flex-wrap: wrap; gap: .5rem; }
  .row { justify-content: space-between; }
  ul, ol { margin: 0; padding-left: 1.25rem; }
  .list { list-style: none; padding: 0; }
  .list li { padding: .65rem 0; border-top: 1px solid #ffffff14; }
  h1, h2, h3, p { margin: 0; overflow-wrap: anywhere; }
  h1 { font-size: clamp(1.55rem, 3vw, 2.4rem); }
  h2 { font-size: 1.1rem; }
  h3 { font-size: .95rem; }
  .muted, label, dt { color: #b0bbcd; }
  .mono, dd, small { overflow-wrap: anywhere; }
  .mono, textarea { font-family: ui-monospace, monospace; }
  .active { color: #69e4d3; }
  label { display: grid; gap: .35rem; min-width: 0; }
  input, select, textarea, button, .button { color: inherit; font: inherit; border: 1px solid #ffffff30; border-radius: .55rem; background: #0c1320; padding: .55rem .7rem; min-width: 0; max-width: 100%; }
  :is(button, .button) { cursor: pointer; text-decoration: none; }
  :is(button, .button):hover:not(:disabled) { background: #24324a; }
  button.primary { background: #68e5d3; border-color: #68e5d3; color: #081816; font-weight: 750; }
  button.primary:hover:not(:disabled) { background: #9af0e4; }
  button.danger { color: #ffc0d6; }
  :disabled { opacity: .6; cursor: default; }
  :focus-visible { outline: 2px solid #6be9d8; outline-offset: 3px; }
  .notice { color: #fdd89d; border-left: 2px solid #fdd89d; padding: .4rem .7rem; }
  .error { color: #ffc3d9; border-left: 2px solid #ff94be; padding: .4rem .7rem; }
  dl { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); margin: 0; gap: .65rem; }
  dd { margin: 0; }
  @media (max-width: 760px) { .columns { grid-template-columns: minmax(0, 1fr); } }
  @media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; animation: none !important; transition: none !important; } }
`,Y=class extends N{constructor(...e){super(...e),this.disabled=!0,this.validation=``}static{this.styles=[J,o`
    .drop { padding: 1rem; border: 1px dashed #658084; border-radius: .8rem; background: #0e1b24; }
    progress { width: 100%; accent-color: #68e5d3; }
  `]}select(e){!e||this.disabled||this.busy||(Re(e)?e.size===0?this.validation=`Файл пуст`:(this.validation=``,this.store?.uploadMedia(e)):this.validation=`Выберите файл MP4, GIF, PNG или JPG`)}get busy(){return this.view?.upload?.phase===`uploading`||this.view?.upload?.phase===`processing`}render(){let e=this.view?.upload;return w`
      <section class="panel stack" aria-labelledby="upload-heading">
        <h2 id="upload-heading">Загрузить файл</h2>
        <label class="drop" @dragover=${e=>e.preventDefault()}
          @drop=${e=>{e.preventDefault(),this.select(e.dataTransfer?.files[0])}}>
          Выберите или перетащите MP4, GIF, PNG или JPG
          <input type="file" accept=".mp4,.gif,.png,.jpg,.jpeg" ?disabled=${this.disabled||this.busy}
            @change=${e=>{let t=e.currentTarget;this.select(t.files?.[0]),t.value=``}}>
        </label>
        ${this.validation?w`<p class="error" role="alert">${this.validation}</p>`:E}
        ${e?.phase===`uploading`?w`
          <div role="status">Передача файла на сервер${e.percent===null?`…`:` · ${Math.round(e.percent)}%`}</div>
          ${e.percent===null?w`<progress aria-label="Передача файла"></progress>`:w`<progress max="100" .value=${e.percent} aria-label="Передача файла"></progress>`}
          <div><button type="button" data-cancel-upload @click=${()=>this.store?.cancelUpload()}>Отменить передачу</button></div>
        `:E}
        ${e?.phase===`processing`?w`
          <p role="status">Сервер обрабатывает файл. Отмена доступна только во время передачи.</p>
        `:E}
        ${e?.phase===`confirmed`?w`<p class="active" role="status">Загрузка подтверждена · ${e.name}</p>`:E}
        ${e?.phase===`cancelled`?w`<p role="status">Передача отменена</p>`:E}
        ${e?.phase===`error`&&!this.validation?w`<p class="error" role="alert">${e.message}</p>`:E}
      </section>
    `}};V([F({attribute:!1})],Y.prototype,`store`,void 0),V([F({attribute:!1})],Y.prototype,`view`,void 0),V([F({type:Boolean})],Y.prototype,`disabled`,void 0),V([I()],Y.prototype,`validation`,void 0),Y=V([P(`upload-zone`)],Y);var X=class extends N{constructor(...e){super(...e),this.dirty=!1,this.busy=!1,this.deleting=null,this.preview=null,this.previewFailed=!1,this.error=``,this.feedback=``,this.revision=-1}static{this.styles=[J,o`
    fieldset { margin: 0; min-width: 0; }
    legend { padding: 0 .4rem; color: #6be9d8; }
    .zones > h2 { grid-column: 1 / -1; }
    .preview img, .preview video { display: block; max-width: min(100%, 40rem); max-height: 24rem; background: #080a10; border-radius: .65rem; }
    ol li + li { margin-top: .55rem; }
    .files .mono { font-size: .85rem; }
  `]}get hasUnsavedChanges(){return this.dirty}connectedCallback(){super.connectedCallback(),this.store?.loadMedia()}willUpdate(e){let t=this.view?.snapshot;e.has(`view`)&&t&&!this.dirty&&t.revision!==this.revision&&(this.draft=Ie(t.state),this.revision=t.revision)}edit(e,t){if(!this.draft)return;let{items:n,mode:r}=t;this.draft={media:this.draft.media.map((t,r)=>r===e&&n?n:t),playback_modes:this.draft.playback_modes.map((t,n)=>n===e&&r?r:t)},this.dirty=!0,this.feedback=``}reset(){let e=this.view?.snapshot;e&&(this.draft=Ie(e.state),this.revision=e.revision,this.dirty=!1)}async save(){if(this.draft&&this.store&&!this.busy){this.busy=!0,this.error=``;try{let e=await this.store.patchScreen(`screen`,{...this.draft},this.revision);e.ok?(this.reset(),this.feedback=`Плейлисты сохранены и поставлены в очередь`):e.error&&(this.error=e.error)}finally{this.busy=!1}}}async removeMedia(){let e=this.deleting;if(e&&this.store&&!this.busy){this.busy=!0,this.error=``;try{await this.store.deleteMedia(e),this.preview?.name===e&&(this.preview=null),this.deleting=null,this.feedback=`Удаление подтверждено · ${e}`}catch(e){this.error=e instanceof Error?e.message:`Ошибка удаления`}finally{this.busy=!1}}}showPreview(e,t){this.preview={name:e,kind:t},this.previewFailed=!1}render(){let e=this.view?.media,t=e?.factory??[],n=(e?.custom??[]).filter(e=>!t.includes(e)),r=!!(e?.adb.available&&e.tools.ffmpeg),i=!!(e?.adb.available&&e.tools.ffprobe),a=this.view?.snapshot?.state,o=[...t,...n];return w`
      <section class="page" aria-labelledby="media-heading">
        <div class="row">
          <h1 id="media-heading">Медиатека</h1>
          <button type="button" @click=${()=>this.store?.loadMedia()}>Обновить список</button>
        </div>
        ${!e&&!this.view?.mediaError?w`<p role="status">Загрузка медиатеки…</p>`:E}
        ${this.view?.mediaError?w`<p class="error" role="alert">${this.view.mediaError}</p>`:E}
        ${this.error?w`<p class="error" role="alert">${this.error}</p>`:E}
        ${this.feedback?w`<p class="active" role="status">${this.feedback}</p>`:E}
        ${e&&!e.adb.available?w`<p class="notice" role="status">ADB недоступен · загрузка и предпросмотр отключены. ${e.adb.reason}</p>`:E}
        ${e&&!e.tools.ffmpeg?w`<p class="notice" role="status">FFmpeg недоступен · предпросмотр и конвертация отключены.</p>`:E}
        ${e&&!e.tools.ffprobe?w`<p class="notice" role="status">FFprobe недоступен · загрузка отключена.</p>`:E}
        <div class="columns">
          ${this.renderCatalog(`Заводские файлы`,t,!1,r)}
          ${this.renderCatalog(`Пользовательские файлы`,n,!0,r)}
        </div>
        ${this.deleting?w`
          <section role="alertdialog" aria-labelledby="delete-media-title" aria-describedby="delete-media-description" class="panel stack">
            <h2 id="delete-media-title">Удалить пользовательский файл?</h2>
            <p id="delete-media-description" class="mono">${this.deleting}</p>
            ${a?.media.flat().includes(this.deleting)?w`<p class="notice">Файл указан в текущем плейлисте.</p>`:E}
            <div class="actions">
              <button type="button" ?disabled=${this.busy} @click=${()=>{this.deleting=null}}>Отмена</button>
              <button type="button" data-confirm-delete class="danger" ?disabled=${this.busy} @click=${this.removeMedia}>Удалить</button>
            </div>
          </section>`:E}
        ${this.preview&&r?w`
          <section class="panel stack preview" aria-labelledby="preview-heading">
            <div class="row"><h2 id="preview-heading">Предпросмотр · ${this.preview.name}</h2>
              <button type="button" @click=${()=>{this.preview=null}}>Закрыть</button>
            </div>
            ${this.previewFailed?w`<p class="error" role="alert">Сервер не смог создать предпросмотр.</p>`:E}
            ${this.preview.kind===`proxy`?w`<video controls preload="metadata" aria-label=${this.preview.name}
                  src=${ze(`proxy`,this.preview.name)} @error=${()=>{this.previewFailed=!0}}></video>`:w`<img alt=${this.preview.name} src=${ze(`thumbnail`,this.preview.name)}
                  @error=${()=>{this.previewFailed=!0}}>`}
          </section>`:E}
        <upload-zone .store=${this.store} .view=${this.view} .disabled=${!i}></upload-zone>
        ${this.draft?w`
          <section class="stack" aria-labelledby="playlist-title">
            <div class="row"><h2 id="playlist-title">Плейлисты</h2><p class="muted">${a?.screen_mode}</p></div>
            <div class="columns zones">
              ${this.draft.media.map((e,t)=>this.renderZone(e,t,o))}
            </div>
            ${this.dirty?w`
              <p class="notice" role="status">${this.view?.snapshot?.revision===this.revision?`Есть несохранённые изменения. Сохранение перезапустит воспроизведение.`:`Конфигурация изменилась. Сбросьте черновик до актуальной версии.`}</p>
            `:E}
            <div class="actions">
              <button type="button" class="primary" data-save-playlists ?disabled=${!this.dirty||this.busy||this.view?.snapshot?.revision!==this.revision} @click=${this.save}>Сохранить плейлисты</button>
              ${this.dirty?w`<button type="button" ?disabled=${this.busy} @click=${this.reset}>Сбросить черновик</button>`:E}
            </div>
          </section>`:E}
      </section>
    `}renderCatalog(e,t,n,r){return w`
      <section class="panel stack files" aria-label=${e}>
        <h2>${e}</h2>
        ${t.length===0?w`<p class="muted">Нет файлов</p>`:w`
          <ul class="list">${t.map(e=>w`<li class="stack">
            <span class="mono">${e}</span>
            <div class="actions">
              <button data-preview type="button" aria-label=${`Предпросмотр ${e}`} ?disabled=${!r}
                @click=${()=>this.showPreview(e,`proxy`)}>Видео</button>
              <button type="button" aria-label=${`Миниатюра ${e}`} ?disabled=${!r}
                @click=${()=>this.showPreview(e,`thumbnail`)}>Миниатюра</button>
              ${n?w`<button type="button" data-delete class="danger" aria-label=${`Удалить ${e}`}
                ?disabled=${!this.view?.snapshot?.device.connected||this.busy}
                @click=${()=>{this.deleting=e,this.error=``}}>Удалить</button>`:E}
            </div>
          </li>`)}</ul>`}
      </section>
    `}renderZone(e,t,n){return w`
      <fieldset data-zone=${t+1} class="panel stack" ?disabled=${this.busy}>
        <legend>Зона ${t+1}</legend>
        <label>Повтор
          <select name=${`playback-mode-${t+1}`}
            @change=${e=>this.edit(t,{mode:e.currentTarget.value})}>
            ${Fe.map(e=>w`<option value=${e} .selected=${q(this.draft.playback_modes[t]===e)}>${e}</option>`)}
          </select>
        </label>
        ${e.length?w`<ol>${e.map((n,r)=>w`<li>
          <div class="row">
            <span class="mono">${n}</span>
            <div class="actions">
              <button type="button" data-move-up ?disabled=${r===0} aria-label=${`Выше ${n}`}
                @click=${()=>this.edit(t,{items:Le(e,r,r-1)})}>↑</button>
              <button type="button" data-move-down ?disabled=${r===e.length-1} aria-label=${`Ниже ${n}`}
                @click=${()=>this.edit(t,{items:Le(e,r,r+1)})}>↓</button>
              <button type="button" aria-label=${`Убрать ${n} из плейлиста`}
                @click=${()=>this.edit(t,{items:e.filter((e,t)=>t!==r)})}>Убрать</button>
            </div>
          </div>
        </li>`)}</ol>`:w`<p class="muted">Плейлист пуст</p>`}
        <label>Добавить файл
          <select ?disabled=${n.every(t=>e.includes(t))}
            @change=${n=>{let r=n.currentTarget;r.value&&this.edit(t,{items:[...e,r.value]}),r.value=``}}>
            <option value="">Выберите из медиатеки</option>
            ${n.filter(t=>!e.includes(t)).map(e=>w`<option value=${e}>${e}</option>`)}
          </select>
        </label>
      </fieldset>
    `}};V([F({attribute:!1})],X.prototype,`store`,void 0),V([F({attribute:!1})],X.prototype,`view`,void 0),V([I()],X.prototype,`draft`,void 0),V([I()],X.prototype,`dirty`,void 0),V([I()],X.prototype,`busy`,void 0),V([I()],X.prototype,`deleting`,void 0),V([I()],X.prototype,`preview`,void 0),V([I()],X.prototype,`previewFailed`,void 0),V([I()],X.prototype,`error`,void 0),V([I()],X.prototype,`feedback`,void 0),X=V([P(`media-page`)],X);function gt(e){let{revision:t,active_profile:n,...r}=e;return r}function _t(e){let t=e.toLowerCase().replace(/[^a-z0-9]+/g,`-`).replace(/^-|-$/g,``);if(t)return t;let n=crypto.getRandomValues(new Uint8Array(8));return`profile-`+Array.from(n,e=>e.toString(16).padStart(2,`0`)).join(``)}function vt(e){let t;try{t=JSON.parse(e)}catch{throw Error(`Файл не содержит корректный JSON`)}if(typeof t!=`object`||!t||Array.isArray(t))throw Error(`JSON профиля должен содержать объект`);return t}function yt(e,t){return typeof t!=`object`||!t||Array.isArray(t)?t:Object.fromEntries(Object.entries(t).sort(([e],[t])=>e.localeCompare(t)))}function bt(e,t){let{slug:n,name:r,factory:i,...a}=t;return JSON.stringify(gt(e),yt)!==JSON.stringify(a,yt)}var Z=class extends N{constructor(...e){super(...e),this.name=``,this.edit=null,this.confirmation=null,this.busy=!1,this.error=``,this.feedback=``}static{this.styles=J}get hasUnsavedChanges(){return!!(this.name.trim()||this.edit&&(this.edit.action===`duplicate`||this.edit.name.trim()!==this.edit.profile.name))}connectedCallback(){super.connectedCallback(),this.store?.loadProfiles()}async run(e,t){if(!this.busy){this.busy=!0,this.error=``,this.feedback=``;try{await e(),this.feedback=t}catch(e){this.error=e instanceof Error?e.message:`Операция с профилем не выполнена`}finally{this.busy=!1}}}create(e){e.preventDefault();let t=this.view?.snapshot?.state,n=this.name.trim();t&&n&&this.store&&this.run(async()=>{await this.store.writeProfile(`create`,{slug:_t(n),name:n,...gt(t)}),this.name=``},`Профиль сохранён`)}saveName(e){e.preventDefault();let t=this.edit,n=t?.name.trim();if(!t||!n||!this.store)return;let r=t.action===`duplicate`?{name:n,slug:_t(n)}:{name:n};this.run(async()=>{await this.store.writeProfile(t.action,r,t.profile.slug),this.edit=null},t.action===`duplicate`?`Копия сохранена`:`Название сохранено`)}importFile(e){let t=e.currentTarget,n=t.files?.[0];t.value=``,n&&this.store&&this.run(async()=>{if(n.size>1048576)throw Error(`JSON профиля превышает 1 МБ`);await this.store.writeProfile(`import`,vt(await n.text()))},`Профиль импортирован`)}apply(e,t=this.view?.snapshot?.revision){t!==void 0&&this.store&&this.run(async()=>{let n=await this.store.applyProfile(e.slug,t);if(!n.ok)throw Error(n.error||`Сервер не подтвердил применение`);this.confirmation=null},`Профиль сохранён и поставлен в очередь`)}saveCurrent(e){let t=this.view?.snapshot?.state;t&&this.store&&this.run(()=>this.store.writeProfile(`update`,gt(t),e.slug),`Текущая конфигурация сохранена в профиль`)}confirm(){let e=this.confirmation;e&&this.store&&(e.action===`apply`?this.apply(e.profile,e.revision):this.run(async()=>{await this.store.deleteProfile(e.profile.slug),this.confirmation=null},`Профиль удалён`))}render(){let e=this.view?.profiles,t=this.view?.snapshot?.state.active_profile,n=e?.find(e=>e.slug===t),r=this.view?.snapshot?.state,i=!!(n&&r&&bt(r,n)),a=e?.filter(e=>e.factory)??[],o=e?.filter(e=>!e.factory)??[],s=this.confirmation;return w`
      <section class="page" aria-labelledby="profiles-heading">
        <h1 id="profiles-heading">Профили</h1>
        ${i?w`<p class="notice" role="status">Есть несохранённые в активном профиле изменения экрана.</p>`:E}
        ${this.hasUnsavedChanges?w`<p class="notice" role="status">Есть несохранённые изменения профиля.</p>`:E}
        ${this.view?.profilesError||this.error?w`<p class="error" role="alert">${this.error||this.view?.profilesError}</p>`:E}
        ${this.feedback?w`<p role="status" class="active">${this.feedback}</p>`:E}
        <div class="columns">
          <form class="panel stack" @submit=${this.create}>
            <h2>Создать из настроек экрана</h2>
            <label>Название профиля
              <input name="profile-name" required maxlength="100" .value=${q(this.name)}
                @input=${e=>{this.name=e.currentTarget.value}}>
            </label>
            <div><button class="primary" data-create type="submit"
              ?disabled=${!r||!this.name.trim()||this.busy}>Создать профиль</button></div>
          </form>
          <section class="panel stack">
            <h2>Импортировать профиль</h2>
            <label>Файл JSON
              <input name="profile-import" type="file" accept=".json,application/json" ?disabled=${this.busy} @change=${this.importFile}>
            </label>
          </section>
        </div>
        ${this.edit?w`
          <form class="panel stack" @submit=${this.saveName} aria-labelledby="edit-profile-title">
            <h2 id="edit-profile-title">${this.edit.action===`rename`?`Переименовать`:`Дублировать`} · ${this.edit.profile.name}</h2>
            <label>Название
              <input name="edit-profile-name" required maxlength="100" .value=${q(this.edit.name)} @input=${e=>{this.edit&&={...this.edit,name:e.currentTarget.value}}}>
            </label>
            <div class="actions">
              <button type="submit" class="primary" data-save-name ?disabled=${!this.edit.name.trim()||this.busy}>Сохранить</button>
              <button type="button" ?disabled=${this.busy} @click=${()=>{this.edit=null}}>Отмена</button>
            </div>
          </form>`:E}
        ${s?w`
          <section role="alertdialog" class="panel stack" aria-labelledby="profile-confirm-title" aria-describedby="profile-confirm-description">
            <h2 id="profile-confirm-title">${s.action===`delete`?`Удалить профиль?`:`Применить другой профиль?`}</h2>
            <p id="profile-confirm-description">${s.profile.name}</p>
            ${s.action===`apply`?w`<p class="notice">Текущая конфигурация не сохранена в активном профиле. Применение заменит её.</p>`:t===s.profile.slug?w`<p class="notice">Экран продолжит использовать текущие настройки после удаления профиля.</p>`:E}
            <div class="actions">
              <button type="button" ?disabled=${this.busy} @click=${()=>{this.confirmation=null}}>Отмена</button>
              <button type="button" data-confirm-delete ?disabled=${this.busy} @click=${this.confirm}>
                ${s.action===`delete`?`Удалить`:`Применить`}
              </button>
            </div>
          </section>`:E}
        ${e?w`<div class="columns">
          ${this.renderList(`Встроенные Miku`,a,t,i)}
          ${this.renderList(`Пользовательские профили`,o,t,i)}
        </div>`:w`
          <p role="status">${this.view?.profilesError?`Список профилей недоступен`:`Загрузка профилей…`}</p>
          ${this.view?.profilesError?w`<div><button type="button" @click=${()=>this.store?.loadProfiles()}>Повторить</button></div>`:E}
        `}
      </section>
    `}renderList(e,t,n,r){return w`
      <section class="panel stack" aria-label=${e}>
        <h2>${e}</h2>
        ${t.length===0?w`<p class="muted">Нет профилей</p>`:w`
          <ul class="list">${t.map(e=>w`
            <li class="stack" data-profile=${e.slug}>
              <div class="row">
                <h3>${e.name}</h3>
                ${n===e.slug?w`<span class="active" aria-current="true">Активный</span>`:E}
              </div>
              <p class="muted">${e.screen_mode} · ${e.media.flat().length} медиа</p>
              <div class="actions">
                <button type="button" data-apply ?disabled=${this.busy||!this.view?.snapshot}
                  @click=${()=>{let t=this.view?.snapshot?.revision;t!==void 0&&(r?this.confirmation={action:`apply`,profile:e,revision:t}:this.apply(e,t))}}>Применить</button>
                <button type="button" data-duplicate ?disabled=${this.busy} @click=${()=>{this.edit={action:`duplicate`,profile:e,name:`${e.name} (копия)`}}}>Дублировать</button>
                <a class="button" data-export href=${Be(e.slug)} download=${`${e.slug}.json`}>Экспорт</a>
                ${e.factory?E:w`
                  <button type="button" data-rename ?disabled=${this.busy}
                    @click=${()=>{this.edit={action:`rename`,profile:e,name:e.name}}}>Переименовать</button>
                  ${n===e.slug&&r?w`<button type="button" ?disabled=${this.busy}
                    @click=${()=>this.saveCurrent(e)}>Сохранить настройки экрана</button>`:E}
                  <button type="button" class="danger" data-delete ?disabled=${this.busy}
                    @click=${()=>{this.confirmation={action:`delete`,profile:e}}}>Удалить</button>
                `}
              </div>
            </li>
          `)}</ul>`}
      </section>`}};V([F({attribute:!1})],Z.prototype,`store`,void 0),V([F({attribute:!1})],Z.prototype,`view`,void 0),V([I()],Z.prototype,`name`,void 0),V([I()],Z.prototype,`edit`,void 0),V([I()],Z.prototype,`confirmation`,void 0),V([I()],Z.prototype,`busy`,void 0),V([I()],Z.prototype,`error`,void 0),V([I()],Z.prototype,`feedback`,void 0),Z=V([P(`profiles-page`)],Z);function xt(e){return!!(e&&typeof e==`object`&&`provider`in e&&typeof e.provider==`string`&&`device`in e&&typeof e.device==`string`&&`channel`in e&&typeof e.channel==`string`)}var St=({provider:e,device:t,channel:n})=>JSON.stringify([e,t,n]),Ct=(e,t)=>e===void 0?`${t} · нет данных`:`${t} ${e?`доступен`:`недоступен`}`;function wt(e,t){let n=new Map;for(let r of t){let{ref:t,measurementId:i,source:a,available:o,metadata:s}=r;if(e===`gpu`&&(t.provider!==`amd`&&t.provider!==`nvidia`||!i.startsWith(`gpu.`))||e===`motherboard`&&(t.provider!==`hwmon`||i!==`motherboard.temperature`||!/^temp\d+$/.test(t.channel)))continue;let c=e===`gpu`?JSON.stringify([t.provider,t.device]):St(t);if(n.has(c))continue;let l=e===`gpu`&&typeof s.name==`string`?s.name:r.label,u=e===`gpu`?`${t.provider} · ${l} · ${t.device}`:`${l} · ${t.device}/${t.channel}${o?``:` · недоступен`}`;n.set(c,{value:c,label:u,ref:t}),e===`motherboard`&&!a&&n.set(c,{value:c,label:`${u} · нет источника`,ref:t})}return[...n.values()]}var Q=class extends N{constructor(...e){super(...e),this.dirty=!1,this.busy=!1,this.error=``,this.feedback=``,this.copied=``,this.revision=-1}static{this.styles=J}get hasUnsavedChanges(){return this.dirty}connectedCallback(){super.connectedCallback(),this.refresh()}willUpdate(e){e.has(`view`)&&!this.dirty&&this.view?.snapshot?.revision!==this.revision&&this.reset()}refresh(){this.store?.ensureSensors(!0),this.store?.loadMedia(),this.store?.loadDiagnostics()}reset(){let e=this.view?.snapshot;if(!e)return;let{refresh_interval:t,temperature_unit:n,sensor_selectors:r}=e.state;this.draft={refresh_interval:String(t),temperature_unit:n,sensor_selectors:r},this.revision=e.revision,this.dirty=!1}edit(e){this.draft&&(this.draft={...this.draft,...e},this.dirty=!0,this.feedback=``)}select(e,t){let n={...this.draft?.sensor_selectors};t?n[e]=t:delete n[e],this.edit({sensor_selectors:n})}async save(e){if(e.preventDefault(),!this.store||!this.draft||!this.dirty||this.busy)return;let t=Number(this.draft.refresh_interval);if(!Number.isFinite(t)||t<=0||t>60)this.error=`Интервал должен быть больше 0 и не более 60 секунд`;else{this.busy=!0,this.error=``;try{let e=await this.store.patchScreen(`telemetry-settings`,{...this.draft,refresh_interval:t},this.revision);e.ok?(this.reset(),this.feedback=`Настройки сохранены и поставлены в очередь`):e.error&&(this.error=e.error)}finally{this.busy=!1}}}get diagnosticsText(){let e=this.view?.diagnostics,t=this.view?.snapshot,n=this.view?.media;return JSON.stringify({security:e?{bindMode:e.security.bindMode,lanEnabled:e.security.lanEnabled,authenticationRequired:e.security.authenticationRequired,trustedProxyCount:e.security.trustedProxyCount,activeSessions:e.security.sessions.active,sessionCapacity:e.security.sessions.capacity}:null,session:e?{required:e.session.required,authenticated:e.session.authenticated,expiresIn:e.session.expiresIn}:null,media:n?{adb:n.adb.available,ffmpeg:n.tools.ffmpeg,ffprobe:n.tools.ffprobe}:null,device:t?{connected:t.device.connected}:null,state:t?{revision:t.revision,interval:t.state.refresh_interval,temperatureUnit:t.state.temperature_unit,streamConnected:this.view?.connected}:null,telemetry:t?{sampled:t.telemetry.sampledAt!==null,availableCount:Object.values(t.telemetry.measurements).filter(e=>e.available).length,errorCount:Object.keys(t.telemetry.errors).length}:null},null,2)}async copyDiagnostics(){try{await navigator.clipboard.writeText(this.diagnosticsText),this.copied=`Диагностика скопирована`}catch{let e=this.renderRoot.querySelector(`textarea`);e?.focus(),e?.select(),this.copied=`Нажмите Ctrl+C или ⌘C, чтобы скопировать выделенный текст`}}render(){let e=this.view?.diagnostics,t=this.view?.media,n=this.view?.snapshot,r=Object.values(n?.telemetry.errors??{}),i=Object.entries(n?.telemetry.measurements??{}),a=[[`CPU`,i.find(([e,t])=>e.startsWith(`cpu.`)&&t.available)?.[1]],[`GPU`,i.find(([e,t])=>e.startsWith(`gpu.`)&&t.available)?.[1]],[`Материнская плата`,n?.telemetry.measurements[`motherboard.temperature`]]];return w`
      <section class="page" aria-labelledby="settings-heading">
        <div class="row">
          <h1 id="settings-heading">Настройки</h1>
          <button type="button" @click=${this.refresh}>Обновить диагностику</button>
        </div>
        <div class="columns">
          <section class="panel stack" aria-labelledby="source-heading">
            <h2 id="source-heading">Текущие источники телеметрии</h2>
            <dl>${a.map(([e,t])=>w`
              <dt>${e}</dt><dd>${xt(t?.ref)?t.ref.provider+` · `:``}
                ${t?.available?t.source||`Источник не указан`:t?.error||`Данные недоступны`}</dd>`)}
            </dl>
            ${r.length?w`<ul class="muted">${r.map(e=>w`<li>${e}</li>`)}</ul>`:E}
          </section>
          ${this.draft?w`
            <form class="panel stack" aria-labelledby="telemetry-settings-title" @submit=${this.save}>
              <h2 id="telemetry-settings-title">Настройки телеметрии</h2>
              ${this.renderSelector(`gpu`,`Провайдер и устройство GPU`)}
              ${this.renderSelector(`motherboard`,`Датчик материнской платы`)}
              <label>Интервал обновления, с
                <input type="number" name="refresh_interval" required min="0.001" max="60" step="any"
                  .value=${q(this.draft.refresh_interval)} @input=${e=>{this.edit({refresh_interval:e.currentTarget.value})}}>
              </label>
              <label>Единица температуры
                <select name="temperature_unit" @change=${e=>{this.edit({temperature_unit:e.currentTarget.value})}}>
                  <option value="Celsius" .selected=${q(this.draft.temperature_unit===`Celsius`)}>°C</option>
                  <option value="Fahrenheit" .selected=${q(this.draft.temperature_unit===`Fahrenheit`)}>°F</option>
                </select>
              </label>
              ${this.dirty&&n?.revision!==this.revision?w`
                <p class="notice" role="status">Конфигурация изменилась. Сбросьте черновик до актуальной версии.</p>`:E}
              ${this.error?w`<p class="error" role="alert">${this.error}</p>`:E}
              ${this.feedback?w`<p class="active" role="status">${this.feedback}</p>`:E}
              <div class="actions">
                <button type="submit" class="primary" data-save-settings ?disabled=${!this.dirty||this.busy||n?.revision!==this.revision}>Сохранить</button>
                ${this.dirty?w`<button type="button" ?disabled=${this.busy} @click=${this.reset}>Сбросить черновик</button>`:E}
              </div>
            </form>`:w`<p role="status">Загрузка настроек телеметрии…</p>`}
        </div>
        <div class="columns">
          <section class="panel stack" aria-labelledby="availability-title">
            <h2 id="availability-title">Инструменты</h2>
            <ul>
              <li>${Ct(t?.adb.available,`ADB`)}</li>
              <li>${Ct(t?.tools.ffmpeg,`FFmpeg`)}</li>
              <li>${Ct(t?.tools.ffprobe,`FFprobe`)}</li>
            </ul>
            ${this.view?.mediaError?w`<p class="error" role="alert">${this.view.mediaError}</p>`:E}
          </section>
          <section class="panel stack" aria-labelledby="access-title">
            <h2 id="access-title">Доступ и сессия</h2>
            ${e?w`
              <dl>
                <dt>Настроенный режим прослушивания</dt><dd>${e.security.bindMode===`lan`?`LAN`:`Только loopback`}</dd>
                <dt>Авторизация</dt><dd>${e.security.authenticationRequired?`Пароль настроен`:e.security.trustedProxyCount?`Доверенный прокси`:`Локальный доступ`}</dd>
                <dt>Текущая сессия</dt><dd>${e.session.required?e.session.authenticated?`Активна`:`Вход требуется`:`Для этого подключения вход не требуется`}</dd>
                <dt>Сессий сервера</dt><dd>${e.security.sessions.active} / ${e.security.sessions.capacity}</dd>
              </dl>`:w`<p role="status">${this.view?.diagnosticsError||`Загрузка статуса доступа…`}</p>`}
            <p class="muted">Адрес прослушивания и пароль меняются в системном файле
              <code>/etc/ryuo-screen/config.toml</code>. Изменения вступают в силу после перезапуска службы.</p>
          </section>
        </div>
        <section class="panel stack" aria-labelledby="diagnostics-title">
          <div class="row"><h2 id="diagnostics-title">Диагностика</h2>
            <button type="button" data-copy-diagnostics @click=${this.copyDiagnostics}>Копировать диагностику</button>
          </div>
          <textarea readonly rows="8" aria-label="Диагностика без секретов" .value=${this.diagnosticsText}></textarea>
          ${this.copied?w`<p role="status">${this.copied}</p>`:E}
        </section>
      </section>
    `}renderSelector(e,t){let n=this.draft?.sensor_selectors[e],r=wt(e,this.view?.sensors??[]),i=xt(n)?e===`gpu`?JSON.stringify([n.provider,n.device]):St(n):``;return xt(n)&&!r.some(e=>e.value===i)&&r.push({value:i,label:`${n.provider} · ${n.device} · ${n.channel} · недоступен`,ref:n}),w`
      <label>${t}
        <select name=${e} @change=${t=>{let n=t.currentTarget.value;this.select(e,r.find(e=>e.value===n)?.ref)}}>
          <option value="" .selected=${q(!i)}>По настройкам службы</option>
          ${r.map(e=>w`<option value=${e.value} .selected=${q(e.value===i)}>${e.label}</option>`)}
        </select>
      </label>
    `}};V([F({attribute:!1})],Q.prototype,`store`,void 0),V([F({attribute:!1})],Q.prototype,`view`,void 0),V([I()],Q.prototype,`draft`,void 0),V([I()],Q.prototype,`dirty`,void 0),V([I()],Q.prototype,`busy`,void 0),V([I()],Q.prototype,`error`,void 0),V([I()],Q.prototype,`feedback`,void 0),V([I()],Q.prototype,`copied`,void 0),Q=V([P(`settings-page`)],Q);var Tt={dashboard:`Dashboard`,screen:`Экран`,media:`Медиатека`,profiles:`Профили`,settings:`Настройки`},$=class extends N{constructor(...e){super(...e),this.store=new qe(new He,new We),this.view=this.store.value,this.page=`dashboard`}static{this.styles=o`
    :host { display: block; min-height: 100vh; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: 1rem clamp(1rem, 4vw, 3rem); border-bottom: 1px solid #ffffff10; background: #090c13dd; backdrop-filter: blur(14px); position: sticky; top: 0; z-index: 2; }
    .brand { display: flex; align-items: center; gap: .7rem; font-weight: 850; letter-spacing: .03em; }
    .glyph { display: grid; place-items: center; width: 2rem; aspect-ratio: 1; border-radius: .65rem; color: #07110f; background: linear-gradient(145deg, #5be3d3, #f265a1); }
    nav { display: flex; flex-wrap: wrap; gap: .35rem; color: #99a6b9; font-size: .9rem; }
    nav button { padding: .4rem .55rem; border: 0; border-bottom: 2px solid transparent; color: #99a6b9; background: transparent; font: inherit; cursor: pointer; }
    nav button[aria-current="page"] { color: #f5f7fb; border-bottom-color: #5be3d3; }
    nav button:focus-visible { outline: 2px solid #5be3d3; outline-offset: 2px; }
    .stream { display: flex; align-items: center; gap: .45rem; color: #9da9ba; font-size: .8rem; }
    .stream::before { content: ""; width: .45rem; height: .45rem; border-radius: 50%; background: #f26c83; }
    .stream.live::before { background: #5de2b0; }
    main { width: min(78rem, calc(100% - 2rem)); margin: 1.2rem auto 3rem; }
    @media (max-width: 860px) { header { flex-wrap: wrap; } nav { order: 3; width: 100%; } }
    @media (max-width: 560px) { header { padding: .65rem .6rem; } nav { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); } nav button { padding-inline: .1rem; font-size: .8rem; } main { width: min(100% - 1rem, 78rem); } }
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; animation: none !important; } }
  `}connectedCallback(){super.connectedCallback(),this.unsubscribe=this.store.subscribe(e=>{this.view=e}),this.store.start()}disconnectedCallback(){this.unsubscribe?.(),this.store.stop(),super.disconnectedCallback()}render(){return w`
      <header>
        <div class="brand"><span class="glyph">IV</span> RYŪŌ SCREEN</div>
        ${this.view.phase===`login`?``:w`
          <nav aria-label="Основная навигация">
            ${Object.keys(Tt).map(e=>w`
              <button type="button" aria-current=${this.page===e?`page`:`false`}
                @click=${()=>this.navigate(e)}>${Tt[e]}</button>`)}
          </nav>`}
        <div class="stream ${this.view.connected?`live`:``}">${this.view.connected?`Live`:`Offline`}</div>
      </header>
      <main>
        ${this.view.phase===`login`?w`<login-view .view=${this.view} @login-submit=${this.onLogin}></login-view>`:this.renderPage()}
      </main>
    `}renderPage(){if(this.view.phase!==`ready`)return w`<dashboard-page .view=${this.view}></dashboard-page>`;switch(this.page){case`screen`:return w`<screen-page .snapshot=${this.view.snapshot} .sensors=${this.view.sensors??[]}
          .controller=${this.store} .mutationError=${this.view.mutationError??null}></screen-page>`;case`media`:return w`<media-page .view=${this.view} .store=${this.store}></media-page>`;case`profiles`:return w`<profiles-page .view=${this.view} .store=${this.store}></profiles-page>`;case`settings`:return w`<settings-page .view=${this.view} .store=${this.store}></settings-page>`;case`dashboard`:return w`<dashboard-page .view=${this.view}></dashboard-page>`}}navigate(e){e!==this.page&&(!this.renderRoot.querySelector(`media-page, profiles-page, settings-page`)?.hasUnsavedChanges||window.confirm(`Покинуть страницу и потерять несохранённые изменения?`))&&(this.page=e)}onLogin(e){this.store.login(e.detail.password)}};V([F({attribute:!1})],$.prototype,`store`,void 0),V([I()],$.prototype,`view`,void 0),V([I()],$.prototype,`page`,void 0),$=V([P(`ryuo-app`)],$);