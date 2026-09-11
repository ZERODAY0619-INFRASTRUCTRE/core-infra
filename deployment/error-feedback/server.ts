import {handleFeedbackRequest} from './error-feedback-handler';
import {feedbackSummary} from './error-feedback';
// A loopback-only collector in the public Caddy namespace. No management
// routes, authentication cookies, admin database or outbound fetches.
Bun.serve({hostname:'127.0.0.1',port:8930,maxRequestBodySize:2048,async fetch(req){
  const path=new URL(req.url).pathname;
  if(path==='/health'&&req.method==='GET'){
    try{feedbackSummary();return Response.json({status:'ok'});}catch{return Response.json({status:'unavailable'},{status:503});}
  }
  if(path==='/api/error-feedback'&&req.method==='POST')return handleFeedbackRequest(req);
  return new Response(null,{status:404});
}});
